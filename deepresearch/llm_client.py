from __future__ import annotations

import json
import time
from typing import Any

import anthropic

_openai_placeholder = None
try:
    import openai
except ImportError:  # pragma: no cover
    class _FakeOpenAIModule:
        class OpenAI:
            pass

    openai = _FakeOpenAIModule()  # type: ignore[assignment]
    _openai_placeholder = _FakeOpenAIModule.OpenAI

try:
    from json_repair import repair_json
except ImportError:
    repair_json = None


def _extract_json_block(text: str) -> str:
    start = text.find("{")
    if start == -1:
        return text
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:]


def extract_and_repair_json(text: str) -> str:
    text = _extract_json_block(text)
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```json") or lines[0] == "```":
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    if repair_json is not None:
        repaired = repair_json(text, return_objects=False)
        if isinstance(repaired, str):
            return repaired
    return text


class _RetryMixin:
    """Exponential back-off retry wrapper for LLM generate calls."""

    def _generate_with_retry(
        self,
        generate_fn: Any,
        max_retries: int = 3,
    ) -> str:
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                return generate_fn()
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    time.sleep(2 ** (attempt - 1))
                    continue
                raise last_error from None


class AnthropicClient(_RetryMixin):
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
    ):
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = anthropic.Anthropic(**kwargs)
        self.model = model

    def generate(
        self,
        prompt: str,
        system: str = "You are a helpful research assistant.",
        max_tokens: int = 4096,
        max_retries: int = 3,
    ) -> str:
        def _call() -> str:
            stream = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system,
                messages=[
                    {"role": "user", "content": [{"type": "text", "text": prompt}]}
                ],
                stream=True,
            )
            chunks: list[str] = []
            for chunk in stream:
                if chunk.type == "content_block_delta" and hasattr(
                    chunk.delta, "text"
                ):
                    chunks.append(chunk.delta.text)
            return "".join(chunks)

        return self._generate_with_retry(_call, max_retries)

    def json(
        self,
        prompt: str,
        system: str = "You are a helpful research assistant.",
        max_tokens: int = 4096,
    ) -> dict:
        text = extract_and_repair_json(self.generate(prompt, system, max_tokens))
        return json.loads(text)


class OpenAIClient(_RetryMixin):
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str | None = None,
    ):
        if _openai_placeholder is not None and openai.OpenAI is _openai_placeholder:
            raise ImportError(
                "The 'openai' package is required for OpenAIClient. "
                "Install it with: pip install openai"
            )
        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self.client = openai.OpenAI(**kwargs)
        self.model = model

    def generate(
        self,
        prompt: str,
        system: str = "You are a helpful research assistant.",
        max_tokens: int = 4096,
        max_retries: int = 3,
    ) -> str:
        def _call() -> str:
            stream = self.client.chat.completions.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt},
                ],
                stream=True,
            )
            chunks: list[str] = []
            for chunk in stream:
                delta = chunk.choices[0].delta
                if hasattr(delta, "content") and delta.content:
                    chunks.append(delta.content)
            return "".join(chunks)

        return self._generate_with_retry(_call, max_retries)

    def json(
        self,
        prompt: str,
        system: str = "You are a helpful research assistant.",
        max_tokens: int = 4096,
    ) -> dict:
        text = extract_and_repair_json(self.generate(prompt, system, max_tokens))
        return json.loads(text)


class LLMClient:
    def __init__(self, config):
        self._anthropic = None
        if getattr(config, "anthropic_api_key", None):
            self._anthropic = AnthropicClient(
                api_key=config.anthropic_api_key,
                model=getattr(config, "anthropic_model", "claude-sonnet-4-20250514"),
                base_url=getattr(config, "anthropic_base_url", None) or None,
            )

        self._openai = None
        if getattr(config, "openai_api_key", None):
            self._openai = OpenAIClient(
                api_key=config.openai_api_key,
                model=getattr(config, "openai_model", "gpt-4o"),
                base_url=getattr(config, "openai_base_url", None) or None,
            )

        self.default_provider = getattr(config, "default_provider", "anthropic")
        self.max_tokens = getattr(config, "max_tokens", 4096)

    def _get_client(self, provider: str | None) -> AnthropicClient | OpenAIClient:
        provider = (provider or self.default_provider).lower()
        if provider == "anthropic":
            if self._anthropic is None:
                raise RuntimeError(
                    "Anthropic provider requested but no anthropic_api_key is configured."
                )
            return self._anthropic
        if provider == "openai":
            if self._openai is None:
                raise RuntimeError(
                    "OpenAI provider requested but no openai_api_key is configured."
                )
            return self._openai
        raise RuntimeError(f"Unknown provider: {provider!r}. Use 'anthropic' or 'openai'.")

    def generate(
        self,
        prompt: str,
        system: str = "You are a helpful research assistant.",
        provider: str | None = None,
        max_tokens: int | None = None,
    ) -> str:
        max_tokens = max_tokens or self.max_tokens
        client = self._get_client(provider)
        return client.generate(prompt, system, max_tokens)

    def json(
        self,
        prompt: str,
        system: str = "You are a helpful research assistant.",
        provider: str | None = None,
        max_tokens: int | None = None,
    ) -> dict:
        max_tokens = max_tokens or self.max_tokens
        client = self._get_client(provider)
        return client.json(prompt, system, max_tokens)
