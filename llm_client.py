from __future__ import annotations
import json
import time
from typing import Optional
import anthropic
import re, json

def fix_json_escapes(text: str) -> str:
    # Enhanced extraction: find first { and last }
    start, end = text.find('{'), text.rfind('}') + 1
    if start != -1 and end != 0:
        text = text[start:end]
    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```json") or lines[0] == "```":
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    # Fix unescaped backslashes before common chars (naive but helpful)
    # WARNING: This is heuristic; proper fix is LLM-side or using JSON mode
    text = re.sub(r'(?<!\\)\\(?!["\\/bfnrtu])', r'\\\\', text)
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
        text = fix_json_escapes(self.generate(prompt, system, max_tokens))
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
        text = fix_json_escapes(self.generate(prompt, system, max_tokens))
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
