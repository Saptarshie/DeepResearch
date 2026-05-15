Here's a comprehensive walkthrough of your entire codebase. I'll organize it by subsystem.

---

## Project Overview

**DeepResearch** is an AI-powered autonomous research agent. You give it a query, and it plans searches, fetches web pages, extracts content, identifies gaps, and synthesizes everything into a publication-quality markdown report — optionally with PDF export.

The project has two main delivery modes:

1. **Standalone**: `caller.py` or `deepresearch/cli.py` — runs a single research job
2. **Web Server**: `server/` — FastAPI multi-user service with SSE live progress, MongoDB persistence, and a Tailwind frontend

---

## Architecture at a Glance

```
deepresearch/              ← Core library (research pipeline)
├── deep_search.py         ← Main orchestration (the conductor)
├── config.py              ← Typed config dataclass + .env loader
├── llm_client.py          ← Anthropic + OpenAI clients
├── planner.py             ← LLM generates search queries
├── searx_client.py        ← SearxNG search engine client
├── fetcher.py             ← HTTP + Playwright (browser) + PDF fetcher
├── extractor.py           ← HTML (Trafilatura) / PDF (PyMuPDF) text extraction
├── frontier.py            ← Priority queue for crawl URLs
├── critic.py              ← LLM identifies knowledge gaps → follow-up searches
├── url_validator.py       ← Block private/loopback/CGNAT URLs
├── schemas.py             ← Pydantic-free dataclasses (SearchResult, Document, etc.)
├── utils.py               ← Dirname sanitization
├── cli.py                 ← CLI entry point
├── mermaid_fixer.py       ← Post-process Mermaid diagram syntax
└── synthesizer/
    ├── __init__.py
    ├── synthesizer.py     ← Orchestrates the 3-stage synthesis
    ├── indexer.py         ← Stage 1: Build topic hierarchy from docs
    ├── overview_builder.py← Stage 2: Generate LLM overviews per topic
    └── report_builder.py  ← Stage 3: Write final report with tables/Mermaid/citations

server/                    ← Multi-user web service
├── main.py                ← FastAPI app + routes
├── research_service.py    ← Background job runner + SSE
├── database.py            ← MongoDB (Motor) connection
├── models.py              ← Pydantic request/response models
├── pdf_generator.py       ← Markdown → PDF via Playwright + Mermaid
├── static/app.js          ← Vanilla JS frontend
├── static/style.css       ← Custom scrollbar styles
└── templates/index.html   ← Tailwind CSS UI

tests/                     ← Test suite (pytest, 15 test files)
```

---

## The Research Pipeline (step by step)

### 1. Entry Points

- **`caller.py`** — The main test harness. Defines a `CUSTOM_CONFIG` dict with your LLM provider settings, and calls `deep_search()` with a progress callback that prints real-time ASCII progress bars.
- **`deepresearch/cli.py`** — A simple CLI that takes a topic string, optionally writes output to a file.

### 2. Configuration (`config.py`)

A `@dataclass` with **~30 fields** covering:

- LLM providers (Anthropic, OpenAI) with API keys, models, base URLs
- Search/fetch settings (concurrency, timeouts, browser enable)
- Synthesis settings (token limits, batch sizes, thresholds)
- Paths (`workspace_dir`, `indexes_dir`)
- Class method `from_env()` reads from `.env` using a `_ENV_MAP` that maps env var names → field names with type converters

### 3. LLM Client (`llm_client.py`)

A **multi-provider abstraction**:

- **`AnthropicClient`** — wraps `anthropic.Anthropic`, streaming response
- **`OpenAIClient`** — wraps `openai.OpenAI`, streaming response
- **`LLMClient`** — Facade that selects provider based on `default_provider` config field
- Both clients provide `.generate()` (returns text) and `.json()` (extracts + repairs JSON from LLM output)
- **JSON repair**: `_extract_json_block()` finds the outermost `{...}` brace pair, strips markdown fences, then runs `json_repair.repair_json()` if available
- **Retry mixin**: 3 attempts with exponential backoff (1s, 2s, 4s)

### 4. Planning (`planner.py`)

- `Planner.make_plan(topic)` calls the LLM with a detailed system prompt
- The LLM returns JSON with: `queries` (max 8, distinct angles), `subquestions`, `source_preferences`, `stop_conditions`
- The query design rules enforce coverage: recent developments, expert debate, data/statistics, historical context, policy/regulatory angle

### 5. Searching (`searx_client.py`)

- `SearxClient.search(query)` → async HTTP GET to SearxNG `{base_url}/search?format=json`
- Returns `list[SearchResult]` with title, URL, snippet, engine
- Cleanup via `close()`, supports async context manager

### 6. Crawl Frontier (`frontier.py`)

- **`CrawlFrontier`** — an `asyncio.PriorityQueue` wrapping `FrontierItem` objects
- Items are pushed with negative priority (higher score = served first)
- Deduplication via `canonical_url` (URL stripped of `#fragment`), depth-limited to `max_depth`
- Scoring in `deep_search.py`: PDFs +1, titles with "research"/"paper"/"docs"/"official"/"report" +1.5, long snippets +0.2

### 7. Fetching (`fetcher.py`)

Three fetch strategies, tried in order:

1. **`fetch_http()`** — httpx with `follow_redirects=True`, custom User-Agent
2. **`fetch_pdf()`** — HTTP download + PyMuPDF (`fitz`) text extraction (up to 50 pages)
3. **`fetch_browser()`** — Playwright Chromium for JavaScript-heavy pages
   - Has both an **async** version (reuses a persistent browser) and a **sync** version (runs in `run_in_executor` to avoid asyncio subprocess issues on Windows)
- `fetch()` orchestrates: tries HTTP first, falls back to browser if content is too short (<500 chars) or after retries exhaust

### 8. Extraction (`extractor.py`)

- `extract_document(html, url)` → uses **Trafilatura** (`bare_extraction`) for HTML → tries to get title, author, date, language, clean text
- `extract_pdf_document(text, url)` → simple first-line-as-title extraction for PDFs

### 9. Gap Analysis (`critic.py`)

- `Critic.find_gaps(question, docs)` runs periodically (every `critique_batch_size` docs)
- Feeds the LLM the question + first 200 chars of each document
- LLM returns JSON: covered subtopics, missing subtopics, contradictions, follow-up queries, `should_research_more` boolean
- **If gaps found**: follow-up search queries are issued, matching URLs get a +0.5 priority boost and are pushed back into the frontier

### 10. Main Orchestrator (`deep_search.py`)

The `deep_search()` async function ties everything together:

```
              ┌─────────────┐
              │   LLM Plan  │
              └──────┬──────┘
                     │ queries
                     ▼
              ┌─────────────┐
              │ SearxNG     │ ◄── multiple parallel searches
              │ (semaphore) │       with concurrency limit
              └──────┬──────┘
                     │ SearchResults
                     ▼
              ┌─────────────┐
              │  Frontier   │
              │ (priority)  │
              └──────┬──────┘
                     │ FrontierItems
                     ▼
        ┌────────────────────────┐
        │  Fetch & Process Loop  │ ◄── async with semaphore
        │  ┌──────────────────┐  │     runs until max_docs
        │  │ HTTP / PDF /     │  │     or frontier empty
        │  │ Browser fallback │  │
        │  └────────┬─────────┘  │
        │           ▼            │
        │  ┌──────────────────┐  │
        │  │ Trafilatura /    │  │
        │  │ PyMuPDF extract  │  │
        │  └────────┬─────────┘  │
        │           ▼            │
        │  ┌──────────────────┐  │
        │  │ Dedup by MD5     │  │
        │  │ (first 5000 ch)  │  │
        │  └────────┬─────────┘  │
        │           ▼            │
        │  ┌──────────────────┐  │
        │  │ Critic (every N) │──┼──► follow-up searches
        │  └──────────────────┘  │
        └───────────┬────────────┘
                    ▼ docs
              ┌─────────────┐
              │ Synthesizer │
              │ 3 stages    │
              └──────┬──────┘
                     ▼
              ┌─────────────┐
              │  Final Report│
              │  (Markdown)  │
              └─────────────┘
```

Key design patterns in the fetch loop:

- **Asyncio semaphores** limit parallel search and fetch operations
- **`asyncio.wait(FIRST_COMPLETED)`** — processes docs as they arrive, keeps the pipeline saturated
- **Cleanup in `finally`** — cancels pending tasks, closes fetcher and searx client

---

## The Synthesis Subsystem (3 stages)

### Stage 1: Indexer (`synthesizer/indexer.py`)

- Processes documents in batches (default 5)
- For each batch, calls the LLM with:
  - The current topic hierarchy (JSON tree)
  - A scratch pad (structured notes)
  - Document excerpts (first 10K chars each)
- LLM returns:
  - `updated_topics_hierarchy` — a nested dict of topics/subtopics (e.g., `{"Photosynthesis": {"Light Reactions": {}, "Calvin Cycle": {}}}`)
  - `extracted_information` — list of `{path, content}` pairs → written to `INDEXES/<sanitized_path>/information.md`
  - `updated_scratch_pad` — structured notes about coverage status, causal chains, cross-references
- Persists: `workspace/topics.json` and `workspace/scratch_pad.md`

### Stage 2: Overview Builder (`synthesizer/overview_builder.py`)

- **Recursive directory walk** from `INDEXES/` root
- Leaf nodes: just return `information.md` content
- Intermediate nodes: concatenate child summaries + local info
- **Root node only**: calls LLM to synthesize into an `overview.md` with:
  - Executive summary
  - Key findings (with source attribution)
  - Core probability/risk assessment table
  - Critical transmission mechanisms (causal chains)
  - Contradictions/debates
  - Gaps/uncertainties

### Stage 3: Report Builder (`synthesizer/report_builder.py`)

The most complex module. Key behaviors:

1. **Intelligent topic ordering** (`_sort_topics_intelligently`):
   
   - For any node with >1 child, asks the LLM to order topics for narrative flow
   - LLM returns a JSON array of topic names
   - Has robust response repair (handles list, dict wrapper, string, and JSON-in-string responses)
   - Falls back to original order if LLM fails

2. **Boundary-aware accumulator**:
   
   - Accumulates topic contexts into a buffer (`self.accumulator`)
   - Flushes to LLM when `min_accumulator_threshold` tokens reached
   - **Only flushes when no parent nodes are still open** (all children of a parent have been processed)
   - **Emergency flush** at 5× threshold even mid-parent

3. **3-layer anti-duplication**:
   
   - **Layer 1**: Boundary-aware flushing prevents splitting parent from children
   - **Layer 2**: Injects already-written headings into the LLM prompt (`anti_dup_prompt`)
   - **Layer 3**: Mechanical post-processing strips duplicate headings from generated content

4. **Rolling summary**: Each flushed section is summarized back into a rolling context, so the LLM knows what was already written

5. **Mermaid fixer**: After the report is written, `fix_all_mermaid()` post-processes all ````mermaid` blocks to fix syntax issues

---

## Web Server (`server/`)

### FastAPI Application (`server/main.py`)

Routes:
| Endpoint | Purpose |
|---|---|
| `GET /` | Web UI |
| `POST /api/research` | Start research job |
| `GET /api/jobs/{username}` | List user's jobs |
| `GET /api/jobs/{username}/{job_id}` | Job detail |
| `GET /api/jobs/{username}/{job_id}/progress` | SSE progress stream |
| `GET /api/jobs/{username}/{job_id}/download?fmt=markdown\|pdf` | Download report |

### Research Service (`server/research_service.py`)

- **`create_job()`** — inserts into MongoDB `jobs` collection, creates an `asyncio.Queue` for SSE
- **`run_research()`** — background task that:
  1. Creates isolated `workspace/<username>` and `INDEXES/<username>` directories
  2. Builds config from request (bring-your-own API key, model, endpoint)
  3. Runs `deep_search()` with a progress callback that writes events to both the asyncio queue and MongoDB
  4. Stores the final report in MongoDB `reports` collection
  5. Cleans up user dirs on completion
- **`event_generator()`** — SSE async generator, yields events with keep-alive pings every 30s

### Database (`server/database.py`)

- Lazy singleton pattern for `AsyncIOMotorClient`
- `jobs_collection()` and `reports_collection()` helpers
- Reads `MONGO_URL` from `.env` or defaults to `mongodb://localhost:27017/deepresearch`

### Models (`server/models.py`)

- **`ResearchRequest`** — 17 fields including provider, API key, model, max_docs, etc.
- **`JobStatus`** — enum: pending/running/completed/failed/cancelled
- **`JobResponse`**, **`JobDetailResponse`**, **`ProgressEvent`**, **`DownloadFormat`**

### PDF Generator (`server/pdf_generator.py`)

- Custom `_md_to_html()` — regex-based markdown-to-HTML converter (headings, code blocks, tables, Mermaid blocks, lists, blockquotes)
- `_generate_pdf_sync()` — uses Playwright to render the HTML in Chromium, waits for Mermaid SVGs to render, then calls `page.pdf()`
- Called via `run_in_executor()` to avoid blocking the event loop

### Frontend (`server/static/app.js` + `templates/index.html` + `style.css`)

- **Tailwind CSS** single-page UI
- Form with username, query, advanced settings collapsible panel
- SSE-connected progress bar with colored log output
- Job history panel with per-job download buttons
- Markdown preview on job completion (first 3000 chars)

---

## Testing (`tests/`)

15 test files using `pytest` + `pytest-asyncio` (auto mode). Test organization mirrors the source:

| Test file                  | What it covers                             |
| -------------------------- | ------------------------------------------ |
| `test_config.py`           | Config dataclass, from_env, dict overrides |
| `test_critic.py`           | Critic gap analysis                        |
| `test_extractor.py`        | HTML/PDF extraction                        |
| `test_fetcher.py`          | PageFetcher (likely mocked)                |
| `test_frontier.py`         | Priority queue, dedup, depth limits        |
| `test_indexer.py`          | Indexer processing                         |
| `test_llm_client.py`       | LLM client, JSON extraction/repair         |
| `test_mermaid_fixer.py`    | Mermaid block fixing                       |
| `test_overview_builder.py` | Overview generation                        |
| `test_planner.py`          | Research plan generation                   |
| `test_report_builder.py`   | Full report building                       |
| `test_searx_client.py`     | SearxNG client                             |
| `test_url_validator.py`    | URL safety checks                          |

---

## Key Design Decisions & Patterns

| Decision                        | Rationale                                                                                              |
| ------------------------------- | ------------------------------------------------------------------------------------------------------ |
| **Sync LLM calls**              | LLM calls are synchronous (Anthropic/OpenAI SDKs); `run_in_executor()` bridges to async                |
| **Priority frontier**           | Higher-scored URLs (research papers, PDFs) are fetched first — maximizes info gain early               |
| **3-layer dedup**               | Repeated section headings were a real problem in early versions; three layers provide defense in depth |
| **Separate workspace per user** | `workspace/<user>` and `INDEXES/<user>` prevents cross-user contamination                              |
| **SSE over WebSocket**          | Simpler for one-way progress streaming; no reconnection complexity                                     |
| **Sync Playwright in executor** | Avoids asyncio subprocess manager issues on Windows                                                    |
| **No Pydantic in core**         | Core uses `@dataclass` for lightweight serialization; Pydantic only in server models                   |
| **JSON repair**                 | LLMs frequently produce malformed JSON; `json_repair` + custom extraction provides robustness          |

---

## Known Bugs / Areas for Improvement

1. **`fetcher.py`** has **dead code** (lines 95-102 are unreachable after `return` on line 94) and a **duplicate method** (`fetch_browser` is defined twice — the async version on line 104 shadows the other).
2. **Large document accumulation**: The indexer passes up to 10K chars per doc, multiplied by batch size. For large batches, this could exceed LLM context windows.
3. **PDF generator cancellation**: `FileResponse` in `download_report()` passes a `BackgroundTasks()` to clean up the temp PDF file, but this is not actually a `BackgroundTasks` instance — it creates a plain class instance that won't auto-clean.
4. **No rate limiting**: The API has no per-user rate limiting; a user could start many concurrent research jobs.
5. **SSE reconnection**: The frontend reconnects on error, but doesn't use `Last-Event-ID` for resumption, so mid-stream progress events could be lost.
6. **No report streaming**: The final report is only available after the entire job completes; there's no incremental streaming of the report content as sections are written.
