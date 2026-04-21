"""OmegaResearcher LLM Client — dual MiniMax+Claude with tool-call support."""
from __future__ import annotations
import json
import re
import time
import anthropic
from omega_researcher.config import Config


# ─── JSON Helpers ──────────────────────────────────────────────────────────────

def fix_json_escapes(text: str) -> str:
    """Extract and normalize JSON from LLM output that may contain markdown fences."""
    # Handle JSON arrays too
    if "[" in text and "{" not in text:
        start, end = text.find("["), text.rfind("]") + 1
    else:
        start, end = text.find("{"), text.rfind("}") + 1

    if start != -1 and end > 0:
        text = text[start:end]

    if text.startswith("```"):
        lines = text.split("\n")
        if lines[0].startswith("```json") or lines[0] == "```":
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    # Fix unescaped backslashes (heuristic)
    text = re.sub(r"(?<!\\)\\(?![\"\\\/bfnrtu])", r"\\\\", text)
    return text


# ─── MiniMax Client ────────────────────────────────────────────────────────────

class MiniMaxClient:
    def __init__(self, api_key: str, model: str, base_url: str):
        self.client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
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
                    messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
                    stream=True,
                )
                text = ""
                for chunk in stream:
                    if chunk.type == "content_block_delta" and hasattr(chunk.delta, "text"):
                        text += chunk.delta.text
                return text
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    time.sleep(2 ** (attempt - 1))
        raise last_error or Exception("MiniMax generate failed")

    def json(self, prompt: str, system: str = "You are a helpful research assistant.", max_tokens: int = 4096) -> dict | list:
        raw = self.generate(prompt, system, max_tokens)
        return json.loads(fix_json_escapes(raw))


# ─── Claude Client ─────────────────────────────────────────────────────────────

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
                    messages=[{"role": "user", "content": [{"type": "text", "text": prompt}]}],
                    stream=True,
                )
                text = ""
                for chunk in stream:
                    if chunk.type == "content_block_delta" and hasattr(chunk.delta, "text"):
                        text += chunk.delta.text
                return text
            except Exception as e:
                last_error = e
                if attempt < max_retries:
                    time.sleep(2 ** (attempt - 1))
        raise last_error or Exception("Claude generate failed")

    def json(self, prompt: str, system: str = "You are a helpful research assistant.", max_tokens: int = 4096) -> dict | list:
        raw = self.generate(prompt, system, max_tokens)
        return json.loads(fix_json_escapes(raw))

    def with_tools(
        self,
        prompt: str,
        tools: list[dict],
        system: str = "You are a helpful research assistant.",
        max_tokens: int = 4096,
    ) -> tuple[str, list[dict]]:
        """
        Generate with tool use enabled.
        Returns (text_response, list_of_tool_calls).
        Used by ActorAgent when it needs the LLM to call MCP tools.
        """
        response = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=[{"role": "user", "content": prompt}],
        )
        text = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                text += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "name": block.name,
                    "input": block.input,
                    "id": block.id,
                })
        return text, tool_calls


# ─── Unified LLM Client ────────────────────────────────────────────────────────

class LLMClient:
    """
    Unified interface for MiniMax (primary) + Claude (high-quality / tool-use).
    Mirrors the original deepresearch LLMClient interface for compatibility.
    """

    def __init__(self, config: Config):
        base_url = getattr(config, "anthropic_base_url", "https://api.minimax.io/anthropic")
        self.minimax = MiniMaxClient(
            api_key=config.minimax_api_key,
            model=config.minimax_model,
            base_url=base_url,
        )
        self.claude = (
            ClaudeClient(api_key=config.anthropic_api_key, model=config.claude_model)
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
    ) -> dict | list:
        max_tokens = max_tokens or self.max_tokens
        if use_claude and self.claude:
            return self.claude.json(prompt, system, max_tokens)
        return self.minimax.json(prompt, system, max_tokens)

    def with_tools(
        self,
        prompt: str,
        tools: list[dict],
        system: str = "You are a helpful research assistant.",
        max_tokens: int | None = None,
    ) -> tuple[str, list[dict]]:
        """Tool-calling — always uses Claude (required for Anthropic tool_use API)."""
        max_tokens = max_tokens or self.max_tokens
        if not self.claude:
            raise RuntimeError("Tool-calling requires ANTHROPIC_API_KEY to be set.")
        return self.claude.with_tools(prompt, tools, system, max_tokens)
