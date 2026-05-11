# DeepResearch

An AI-powered deep research agent that autonomously plans, searches, fetches, critiques, and synthesizes publication-quality research reports.

## Overview

DeepResearch takes a research query and turns it into a comprehensive markdown report by:

1. **Planning** — LLM generates targeted search queries
2. **Searching** — Queries SearxNG for relevant documents
3. **Fetching** — Concurrently downloads pages with HTTP + Playwright fallback
4. **Extracting** — Extracts clean text from HTML and PDFs
5. **Critiquing** — Identifies gaps and spawns follow-up searches
6. **Synthesizing** — Builds a topic hierarchy, generates overviews, and writes the final report with tables, Mermaid diagrams, and citations

## Features

- **Multi-provider LLM support** — Anthropic Claude, OpenAI GPT, and OpenAI-compatible APIs (via `base_url`)
- **Concurrent execution** — Bounded async fetch/search with `asyncio.Semaphore`
- **Smart content extraction** — HTML via Trafilatura, PDFs via PyMuPDF, browser fallback via Playwright
- **Gap analysis** — Critic module finds missing coverage and triggers follow-up searches
- **Anti-duplication** — 3-layer defense against repeated headings in generated reports:
  1. Boundary-aware flushing (flush only when parent branches complete)
  2. Prompt-level deduplication (injects already-written headings into LLM prompt)
  3. Mechanical post-processing (strips duplicate headings before writing to disk)
- **Intelligent topic ordering** — LLM reorders topics at every hierarchy level for narrative flow
- **Rich report formatting** — Markdown tables, Mermaid diagrams, LaTeX math, blockquotes, inline citations
- **Live progress tracking** — Callback system with timestamps and ASCII progress bars
- **Configurable** — Dict overrides, `.env` file, or environment variables

## Installation

```bash
pip install -e .
```

Install browser support (optional, for JS-heavy sites):
```bash
playwright install chromium
```

## Quick Start

### 1. Configure

Create a `.env` file:

```env
# Required: at least one LLM provider
ANTHROPIC_API_KEY=sk-ant-...
# OPENAI_API_KEY=sk-...

# Optional: SearxNG instance (default: localhost:8080)
SEARXNG_BASE_URL=http://localhost:8080
```

Or pass a config dict:

```python
from deepresearch import deep_search

result = await deep_search(
    "How does photosynthesis work?",
    config={
        "openai_api_key": "sk-...",
        "openai_model": "gpt-4o",
        "default_provider": "openai",
        "max_docs": 10,
    },
)
```

### 2. Run

```bash
python caller.py
```

Or programmatically:

```python
import asyncio
from deepresearch import deep_search

async def main():
    report = await deep_search(
        "Create a detailed research paper on quantum computing error correction",
        config={"max_docs": 20, "max_depth": 2},
    )
    print(report)

asyncio.run(main())
```

### 3. Fix Mermaid in existing reports

```bash
python fix_existing_mermaid_report.py ./outputs/my_report.md
```

## Architecture

```
deepresearch/
├── __init__.py          # Public API exports
├── deep_search.py       # Main orchestration loop
├── config.py            # Configuration dataclass + .env loader
├── llm_client.py        # Anthropic + OpenAI clients with JSON repair
├── planner.py           # Query planning via LLM
├── searx_client.py      # SearxNG search client
├── fetcher.py           # HTTP fetch + Playwright fallback
├── extractor.py         # HTML/PDF text extraction
├── critic.py            # Gap analysis + follow-up queries
├── frontier.py          # Priority crawl frontier
├── url_validator.py     # URL safety checks
├── schemas.py           # Pydantic/dataclass models
├── utils.py             # Sanitization helpers
├── cli.py               # CLI entry point
├── mermaid_fixer.py     # Post-process Mermaid blocks
└── synthesizer/
    ├── __init__.py      # Synthesizer orchestrator
    ├── indexer.py       # Build topic hierarchy from documents
    ├── overview_builder.py  # Generate section overviews
    └── report_builder.py    # Write final markdown report
```

## Configuration

All config fields (with defaults):

| Field | Default | Description |
|-------|---------|-------------|
| `default_provider` | `"anthropic"` | `"anthropic"` or `"openai"` |
| `anthropic_api_key` | `""` | Anthropic API key |
| `anthropic_model` | `"claude-sonnet-4-20250514"` | Anthropic model name |
| `anthropic_base_url` | `"https://api.anthropic.com"` | Anthropic-compatible endpoint |
| `openai_api_key` | `""` | OpenAI API key |
| `openai_model` | `"gpt-4o"` | OpenAI model name |
| `openai_base_url` | `"https://api.openai.com/v1"` | OpenAI-compatible endpoint |
| `searxng_base_url` | `"http://localhost:8080"` | SearxNG instance URL |
| `max_docs` | `100` | Stop after fetching N documents |
| `max_depth` | `2` | Crawl depth for linked pages |
| `fetch_timeout` | `20.0` | HTTP timeout in seconds |
| `fetch_concurrency` | `10` | Max parallel fetches |
| `search_concurrency` | `5` | Max parallel SearxNG queries |
| `browser_wait_ms` | `2000` | Playwright wait after page load |
| `enable_browser` | `True` | Enable headless browser fallback |
| `enable_pdf_extraction` | `True` | Extract text from PDFs |
| `min_content_length` | `500` | Min HTML length before browser fallback |
| `critique_batch_size` | `10` | Run critic every N documents |
| `max_tokens` | `16384` | LLM output token limit |
| `synthesizer_max_tokens` | `100000` | Report section token limit |
| `max_indexer_depth` | `3` | Max topic hierarchy depth |
| `indexer_batch_size` | `5` | Documents per indexer LLM call |
| `min_accumulator_threshold` | `400` | Token threshold before flushing report |
| `indexes_dir` | `"INDEXES"` | On-disk topic tree folder |
| `workspace_dir` | `"workspace"` | Scratch pad + final report folder |
| `log_level` | `"INFO"` | DEBUG, INFO, WARNING, ERROR |

Load from `.env`, override with dict:

```python
from deepresearch import Config

# Loads from .env automatically
cfg = Config.from_env()

# Override specific fields
cfg = Config.from_env({"max_docs": 20, "fetch_concurrency": 5})
```

## Progress Callbacks

The `deep_search()` function accepts a `progress_callback(event_type, data)` for live updates:

```python
def my_callback(event_type: str, data: dict):
    match event_type:
        case "plan":
            print(f"Generated {len(data['queries'])} search queries")
        case "document":
            print(f"Fetched: {data['title']}")
        case "gaps":
            print(f"Found {len(data['missing'])} gaps, spawning follow-ups")
        case "synth_report_section":
            print(f"Writing section #{data['section_number']}: {data['section_title']}")
        case "complete":
            print(f"Done! Report length: {data['report_length']} chars")

await deep_search("...", progress_callback=my_callback)
```

**Event types:** `status`, `plan`, `search`, `document`, `gaps`, `warning`, `complete`, `synth_indexer_batch`, `synth_indexer_complete`, `synth_overview`, `synth_report_start`, `synth_report_section`, `synth_report_complete`.

## Testing

```bash
pytest tests/ -q
```

Lint:
```bash
ruff check deepresearch/ tests/
```

## Requirements

- Python >= 3.11
- SearxNG instance (or public instance) for web search
- Anthropic and/or OpenAI API key

## License

MIT
