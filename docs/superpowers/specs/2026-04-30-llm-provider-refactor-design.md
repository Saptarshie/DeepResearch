# LLM Provider Refactor Design

## Goal

Replace the existing `MiniMaxClient` + `ClaudeClient` dual-provider setup with a clean, two-provider architecture:
- **Anthropic** (Messages API, via `anthropic` SDK)
- **OpenAI-compatible** (via `openai` SDK, supports OpenAI, local proxies, etc.)

Remove the `MiniMaxClient` entirely. Endpoint URLs and API keys must be driven from `Config` / `.env`.

## Config Changes

### Remove from `Config`
- `minimax_api_key`
- `minimax_model`
- `anthropic_base_url` (renamed to `anthropic_base_url` stays, but we also need `openai_base_url`)

### Add to `Config`
- `anthropic_model: str = "claude-sonnet-4-20250514"`
- `openai_api_key: str = ""`
- `openai_model: str = "gpt-4o"`
- `openai_base_url: str = "https://api.openai.com/v1"`
- `default_provider: str = "anthropic"`

### Update `_ENV_MAP`
Remove `MINIMAX_API_KEY`, `MINIMAX_MODEL`. Add:
- `ANTHROPIC_MODEL`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `OPENAI_BASE_URL`
- `DEFAULT_PROVIDER`

## LLM Client Architecture

### `AnthropicClient`
- Renamed from `ClaudeClient`.
- Constructor: `(api_key: str, model: str, base_url: str | None = None)`
- Uses `anthropic.Anthropic(api_key=api_key, base_url=base_url)`
- `generate(prompt, system, max_tokens, max_retries) -> str`
- `json(prompt, system, max_tokens) -> dict`

### `OpenAIClient` (new)
- Constructor: `(api_key: str, model: str, base_url: str | None = None)`
- Uses `openai.OpenAI(api_key=api_key, base_url=base_url)`
- Same `generate` / `json` interface as `AnthropicClient`
- Uses `client.chat.completions.create(..., stream=True)` and accumulates `chunk.choices[0].delta.content`
- Same exponential back-off retry logic

### `LLMClient`
- Holds both `anthropic` and `openai` client instances (only if the corresponding API key is provided).
- `generate(prompt, system=..., provider=None, max_tokens=None)`:
  - `provider` is a string: `"anthropic"`, `"openai"`, or `None` (uses `self.default_provider`)
  - If the requested provider is not available (no API key configured), raises `RuntimeError` with a clear message.
- `json(...)` delegates to `generate(...)` + `extract_and_repair_json`

## Call Site Updates

Replace all `use_claude=True` with explicit `provider="anthropic"`:

| File | Current | New |
|------|---------|-----|
| `critic.py` | `self.llm.json(..., use_claude=True)` | `self.llm.json(..., provider="anthropic")` |
| `indexer.py` | `self.llm.json(..., use_claude=True, max_tokens=8000)` | `self.llm.json(..., provider="anthropic", max_tokens=8000)` |
| `overview_builder.py` | `self.llm.generate(..., use_claude=True, max_tokens=...)` | `self.llm.generate(..., provider="anthropic", max_tokens=...)` |
| `report_builder.py` | `self.llm.generate(..., use_claude=True, max_tokens=...)` | `self.llm.generate(..., provider="anthropic", max_tokens=...)` |
| `report_builder.py` (summary) | `self.llm.generate(...)` | keep as-is (uses default provider) |

No changes needed in `deep_search.py`, `planner.py`, `cli.py` — they already rely on the default.

## Dependency Update

Add `openai>=1.0.0` to `pyproject.toml` `[project] dependencies`.

## Test Updates

- Update `tests/test_config.py`: remove `minimax` env var references; add tests for `openai_api_key`, `default_provider`.
- Add `tests/test_llm_client.py` tests for provider selection:
  - `test_llm_client_uses_default_provider`
  - `test_llm_client_raises_when_provider_unavailable`
  - `test_llm_client_allows_explicit_provider_override`
  - `test_openai_client_generate_makes_request` (mock `openai.OpenAI`)

## Backwards Compatibility

This is a **breaking change** for consumers who previously relied on `Config.minimax_api_key` / `minimax_model`. They must migrate to `openai_api_key` / `openai_model`. The `.env.example` (if we had one) would need updating, but there is no `.env.example` in the repo currently.
