# LLM Provider Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace MiniMaxClient + ClaudeClient with AnthropicClient + OpenAIClient, driven by Config/.env, with `provider` string parameter.

**Architecture:** Two concrete LLM clients (`AnthropicClient`, `OpenAIClient`) share a common interface. `LLMClient` orchestrates which one to use based on a `provider` parameter (`"anthropic"` or `"openai"`). Configuration (API keys, models, base URLs) is centralized in `Config` and read from `.env`.

**Tech Stack:** Python 3.11+, `anthropic` SDK, `openai` SDK, `pytest`

---

## File Structure

| File | Responsibility | Action |
|------|---------------|--------|
| `deepresearch/config.py` | Centralized configuration with env parsing | Modify |
| `deepresearch/llm_client.py` | All LLM client classes (`AnthropicClient`, `OpenAIClient`, `LLMClient`) | Rewrite |
| `deepresearch/planner.py` | Calls `llm.json()` with default provider | No change needed |
| `deepresearch/critic.py` | Calls `llm.json(..., use_claude=True)` | Modify |
| `deepresearch/synthesizer/indexer.py` | Calls `llm.json(..., use_claude=True)` | Modify |
| `deepresearch/synthesizer/overview_builder.py` | Calls `llm.generate(..., use_claude=True)` | Modify |
| `deepresearch/synthesizer/report_builder.py` | Calls `llm.generate(..., use_claude=True)` | Modify |
| `deepresearch/deep_search.py` | Instantiates `LLMClient`, `Planner`, `Critic` | No change needed |
| `pyproject.toml` | Project dependencies | Modify |
| `tests/test_config.py` | Config tests | Modify |
| `tests/test_llm_client.py` | LLM client tests | Rewrite |

---

### Task 1: Update Config dataclass

**Files:**
- Modify: `deepresearch/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Remove minimax fields and add openai/anthropic fields**

In `deepresearch/config.py`, make these changes:

**Remove from `_ENV_MAP`:**
- `MINIMAX_API_KEY`
- `MINIMAX_MODEL`

**Add to `_ENV_MAP`:**
```python
"ANTHROPIC_MODEL": ("anthropic_model", str),
"OPENAI_API_KEY": ("openai_api_key", str),
"OPENAI_MODEL": ("openai_model", str),
"OPENAI_BASE_URL": ("openai_base_url", str),
"DEFAULT_PROVIDER": ("default_provider", str),
```

**Remove from dataclass fields:**
- `minimax_api_key: str = ""`
- `minimax_model: str = "MiniMax-M2.7"`

**Add to dataclass fields:**
```python
anthropic_model: str = "claude-sonnet-4-20250514"
openai_api_key: str = ""
openai_model: str = "gpt-4o"
openai_base_url: str = "https://api.openai.com/v1"
default_provider: str = "anthropic"
```

- [ ] **Step 2: Update test_config.py**

In `tests/test_config.py`:
- Remove `"MINIMAX_API_KEY"` and `"MINIMAX_MODEL"` from the `env_vars` list in `test_config_from_env_uses_defaults`
- Add `"ANTHROPIC_MODEL"`, `"OPENAI_API_KEY"`, `"OPENAI_MODEL"`, `"OPENAI_BASE_URL"`, `"DEFAULT_PROVIDER"` to that list
- Add a new test:

```python
def test_config_default_provider_defaults_to_anthropic() -> None:
    cfg = Config()
    assert cfg.default_provider == "anthropic"
```

- [ ] **Step 3: Run tests to verify config changes**

Run: `pytest tests/test_config.py -v`
Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add deepresearch/config.py tests/test_config.py
git commit -m "feat: replace minimax config with openai + anthropic config fields"
```

---

### Task 2: Rewrite llm_client.py

**Files:**
- Rewrite: `deepresearch/llm_client.py`
- Test: `tests/test_llm_client.py`

- [ ] **Step 1: Write the failing test for OpenAIClient**

In `tests/test_llm_client.py`, replace the entire file with:

```python
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from deepresearch.llm_client import AnthropicClient, LLMClient, OpenAIClient, extract_and_repair_json


def test_extract_and_repair_json_strips_markdown_fence() -> None:
    raw = '```json\n{"key": "value"}\n```'
    result = extract_and_repair_json(raw)
    assert result == '{"key": "value"}'


def test_extract_and_repair_json_repairs_unescaped_backslashes() -> None:
    raw = r'{"path": "C:\hello\world"}'
    result = extract_and_repair_json(raw)
    parsed = json.loads(result)
    assert parsed["path"] == r"C:\hello\world"


def test_anthropic_client_generate_makes_request() -> None:
    with patch("deepresearch.llm_client.anthropic.Anthropic") as MockAnthropic:
        mock_client = MagicMock()
        mock_stream = [
            MagicMock(type="content_block_delta", delta=MagicMock(text="Hello ")),
            MagicMock(type="content_block_delta", delta=MagicMock(text="world")),
        ]
        mock_client.messages.create.return_value = iter(mock_stream)
        MockAnthropic.return_value = mock_client

        client = AnthropicClient(api_key="test-key", model="claude-test")
        result = client.generate("prompt", "system", max_tokens=100)

        assert result == "Hello world"
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-test"
        assert call_kwargs["max_tokens"] == 100
        assert call_kwargs["system"] == "system"


def test_openai_client_generate_makes_request() -> None:
    with patch("deepresearch.llm_client.openai.OpenAI") as MockOpenAI:
        mock_client = MagicMock()
        mock_chunk1 = MagicMock()
        mock_chunk1.choices = [MagicMock(delta=MagicMock(content="Hello "))]
        mock_chunk2 = MagicMock()
        mock_chunk2.choices = [MagicMock(delta=MagicMock(content="world"))]
        mock_client.chat.completions.create.return_value = iter([mock_chunk1, mock_chunk2])
        MockOpenAI.return_value = mock_client

        client = OpenAIClient(api_key="test-key", model="gpt-test")
        result = client.generate("prompt", "system", max_tokens=100)

        assert result == "Hello world"
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-test"
        assert call_kwargs["max_tokens"] == 100


def test_llm_client_uses_default_provider() -> None:
    with patch("deepresearch.llm_client.anthropic.Anthropic") as MockAnthropic:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = iter([])
        MockAnthropic.return_value = mock_client

        config = MagicMock()
        config.anthropic_api_key = "ak"
        config.anthropic_model = "claude-test"
        config.anthropic_base_url = None
        config.openai_api_key = ""
        config.openai_model = "gpt-test"
        config.openai_base_url = "https://api.openai.com/v1"
        config.default_provider = "anthropic"
        config.max_tokens = 1000

        llm = LLMClient(config)
        llm.generate("hello")

        mock_client.messages.create.assert_called_once()


def test_llm_client_raises_when_provider_unavailable() -> None:
    config = MagicMock()
    config.anthropic_api_key = ""
    config.openai_api_key = ""
    config.default_provider = "anthropic"
    config.max_tokens = 1000

    llm = LLMClient(config)
    try:
        llm.generate("hello")
        assert False, "Expected RuntimeError"
    except RuntimeError as e:
        assert "anthropic" in str(e).lower()


def test_llm_client_allows_explicit_provider_override() -> None:
    with patch("deepresearch.llm_client.openai.OpenAI") as MockOpenAI:
        mock_client = MagicMock()
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock(delta=MagicMock(content="ok"))]
        mock_client.chat.completions.create.return_value = iter([mock_chunk])
        MockOpenAI.return_value = mock_client

        config = MagicMock()
        config.anthropic_api_key = ""
        config.anthropic_model = "claude-test"
        config.anthropic_base_url = None
        config.openai_api_key = "ok"
        config.openai_model = "gpt-test"
        config.openai_base_url = "https://api.openai.com/v1"
        config.default_provider = "anthropic"
        config.max_tokens = 1000

        llm = LLMClient(config)
        result = llm.generate("hello", provider="openai")
        assert result == "ok"
```

Run: `pytest tests/test_llm_client.py -v`
Expected: FAIL with import errors (classes don't exist yet).

- [ ] **Step 2: Rewrite llm_client.py**

Replace the entire `deepresearch/llm_client.py` with:

```python
from __future__ import annotations

import json
import time
from typing import Any

import anthropic

try:
    import openai
except ImportError:  # pragma: no cover
    openai = None  # type: ignore[assignment]

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
                raise
        raise last_error or Exception("Generate failed after retries")


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
            response_text = ""
            for chunk in stream:
                if chunk.type == "content_block_delta" and hasattr(
                    chunk.delta, "text"
                ):
                    response_text += chunk.delta.text
            return response_text

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
        if openai is None:
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
            response_text = ""
            for chunk in stream:
                delta = chunk.choices[0].delta
                if hasattr(delta, "content") and delta.content:
                    response_text += delta.content
            return response_text

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
```

- [ ] **Step 3: Run tests to verify llm_client**

Run: `pytest tests/test_llm_client.py -v`
Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add deepresearch/llm_client.py tests/test_llm_client.py
git commit -m "feat: replace minimax with openai + anthropic clients and provider selection"
```

---

### Task 3: Update call sites (use_claude -> provider)

**Files:**
- Modify: `deepresearch/critic.py`
- Modify: `deepresearch/synthesizer/indexer.py`
- Modify: `deepresearch/synthesizer/overview_builder.py`
- Modify: `deepresearch/synthesizer/report_builder.py`

- [ ] **Step 1: Update critic.py**

In `deepresearch/critic.py`, line 42:

Old:
```python
data = self.llm.json(prompt, system=SYSTEM_PROMPT, use_claude=True)
```

New:
```python
data = self.llm.json(prompt, system=SYSTEM_PROMPT, provider="anthropic")
```

- [ ] **Step 2: Update indexer.py**

In `deepresearch/synthesizer/indexer.py`, line 79-84:

Old:
```python
response = self.llm.json(
    prompt,
    system=system_prompt,
    use_claude=True,
    max_tokens=8000
)
```

New:
```python
response = self.llm.json(
    prompt,
    system=system_prompt,
    provider="anthropic",
    max_tokens=8000,
)
```

- [ ] **Step 3: Update overview_builder.py**

In `deepresearch/synthesizer/overview_builder.py`, line 55-60:

Old:
```python
overview_content = self.llm.generate(
    prompt,
    system=system_prompt,
    use_claude=True,
    max_tokens=self.config.max_tokens
)
```

New:
```python
overview_content = self.llm.generate(
    prompt,
    system=system_prompt,
    provider="anthropic",
    max_tokens=self.config.max_tokens,
)
```

- [ ] **Step 4: Update report_builder.py**

In `deepresearch/synthesizer/report_builder.py`, line 71-76:

Old:
```python
section_content = self.llm.generate(
    prompt,
    system=system_prompt,
    use_claude=True,
    max_tokens=self.config.max_tokens
)
```

New:
```python
section_content = self.llm.generate(
    prompt,
    system=system_prompt,
    provider="anthropic",
    max_tokens=self.config.max_tokens,
)
```

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: All existing tests pass (no new failures from these changes).

- [ ] **Step 6: Commit**

```bash
git add deepresearch/critic.py deepresearch/synthesizer/indexer.py deepresearch/synthesizer/overview_builder.py deepresearch/synthesizer/report_builder.py
git commit -m "refactor: replace use_claude=True with provider='anthropic' in all call sites"
```

---

### Task 4: Add openai dependency to pyproject.toml

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add openai to dependencies**

In `pyproject.toml`, in the `[project] dependencies` list, add:
```toml
"openai>=1.0.0",
```

It should be placed alphabetically near the top:
```toml
dependencies = [
    "anthropic>=0.30.0",
    "httpx>=0.27.0",
    "openai>=1.0.0",
    "playwright>=1.45.0",
    "python-dotenv>=1.0.0",
    "trafilatura>=1.12.0",
    "json-repair>=0.25.0",
]
```

- [ ] **Step 2: Commit**

```bash
git add pyproject.toml
git commit -m "chore: add openai dependency"
```

---

### Task 5: Final verification

- [ ] **Step 1: Run full test suite**

Run: `pytest tests/ -v`
Expected: All tests pass.

- [ ] **Step 2: Run ruff**

Run: `ruff check deepresearch/ tests/`
Expected: No new errors introduced (existing baseline errors are acceptable).

- [ ] **Step 3: Commit**

```bash
git commit -m "test: verify full suite passes after LLM provider refactor" --allow-empty
```

---

## Self-Review Checklist

1. **Spec coverage:**
   - ✅ Remove MiniMaxClient — Task 2
   - ✅ Add AnthropicClient (renamed from ClaudeClient) with configurable base_url — Task 2
   - ✅ Add OpenAIClient with openai SDK — Task 2
   - ✅ LLMClient uses `provider` parameter — Task 2
   - ✅ Config has openai fields and default_provider — Task 1
   - ✅ Call sites updated — Task 3
   - ✅ pyproject.toml updated — Task 4
   - ✅ Tests updated — Task 1, 2

2. **Placeholder scan:** No TBD/TODO/fill-in-details found.

3. **Type consistency:**
   - `LLMClient.generate()` signature: `(prompt, system, provider, max_tokens)` — consistent across all call sites
   - `AnthropicClient` and `OpenAIClient` both have `generate()` and `json()` methods with identical signatures
   - Config field names match `_ENV_MAP` keys
