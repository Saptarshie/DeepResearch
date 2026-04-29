from __future__ import annotations

import json
import time

import anthropic

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

class MiniMaxClient:
    def __init__(self, api_key: str, model: str, base_url: str):
        self.client = anthropic.Anthropic(
            api_key=api_key,
            base_url=base_url,
        )
        self.model = model

    def generate(
        self,
        prompt: str,
        system: str = "You are a helpful research assistant.",
        max_tokens: int = 4096,
        max_retries: int = 3,
    ) -> str:
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                stream = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[
                        {"role": "user", "content": [{"type": "text", "text": prompt}]}
                    ],
                    stream=True,
                )
                response_text = ""
                for chunk in stream:
                    if chunk.type == "content_block_delta" and hasattr(
                        chunk.delta, "text"
                    ):
                        response_text += chunk.delta.text
                return response_text
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    time.sleep(2 ** (attempt - 1))
                    continue
                raise
        raise last_error or Exception("Generate failed after retries")

    def json(
        self,
        prompt: str,
        system: str = "You are a helpful research assistant.",
        max_tokens: int = 4096,
    ) -> dict:
        text = extract_and_repair_json(self.generate(prompt, system, max_tokens))
        return json.loads(text)


class ClaudeClient:
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def generate(
        self,
        prompt: str,
        system: str = "You are a helpful research assistant.",
        max_tokens: int = 4096,
        max_retries: int = 3,
    ) -> str:
        last_error = None
        for attempt in range(1, max_retries + 1):
            try:
                stream = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    system=system,
                    messages=[
                        {"role": "user", "content": [{"type": "text", "text": prompt}]}
                    ],
                    stream=True,
                )
                response_text = ""
                for chunk in stream:
                    if chunk.type == "content_block_delta" and hasattr(
                        chunk.delta, "text"
                    ):
                        response_text += chunk.delta.text
                return response_text
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    time.sleep(2 ** (attempt - 1))
                    continue
                raise
        raise last_error or Exception("Generate failed after retries")

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
        base_url = getattr(
            config, "anthropic_base_url", "https://api.minimax.io/anthropic"
        )
        self.minimax = MiniMaxClient(
            api_key=config.minimax_api_key,
            model=config.minimax_model,
            base_url=base_url,
        )
        self.claude = (
            ClaudeClient(api_key=config.anthropic_api_key)
            if config.anthropic_api_key
            else None
        )
        self.use_claude = bool(config.anthropic_api_key)
        self.max_tokens = config.max_tokens

    def generate(
        self,
        prompt: str,
        system: str = "You are a helpful research assistant.",
        use_claude: bool = False,
        max_tokens: int | None = None,
    ) -> str:
        max_tokens = max_tokens or self.max_tokens
        if use_claude and self.claude:
            return self.claude.generate(prompt, system, max_tokens)
        return self.minimax.generate(prompt, system, max_tokens)

    def json(
        self,
        prompt: str,
        system: str = "You are a helpful research assistant.",
        use_claude: bool = False,
        max_tokens: int | None = None,
    ) -> dict:
        max_tokens = max_tokens or self.max_tokens
        if use_claude and self.claude:
            return self.claude.json(prompt, system, max_tokens)
        return self.minimax.json(prompt, system, max_tokens)
