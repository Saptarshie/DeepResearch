#!/usr/bin/env python
"""Test script for DeepSearch Research System.

All configuration options are exposed below. Values set here override
anything loaded from the environment / .env file.

To run:
    python caller.py
"""

from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

from deepresearch import deep_search


# ---------------------------------------------------------------------------
# Full configuration dictionary – every key mirrors the Config dataclass.
# Comment out any line you want to fall back to the default (or .env value).
# ---------------------------------------------------------------------------
CUSTOM_CONFIG: dict[str, object] = {
    # ------------------------------------------------------------------
    # LLM Provider Settings
    # ------------------------------------------------------------------
    # "anthropic_api_key": "",           # set via .env or leave blank
    # "anthropic_base_url": "https://api.minimax.io/anthropic",
    # "anthropic_model": "claude-sonnet-4-20250514",
    "openai_api_key": "sk-PnHm6w905QCn6sDeRnOfj0OtZWWaC6BZx56EvOdr9Bkr055frGXGcrNEF641Rz3C",                # set via .env or leave blank
    "openai_base_url": "https://opencode.ai/zen/go/v1",
    "openai_model": "minimax-m2.7",
    "default_provider": "openai",     # "anthropic" | "openai"

    # ------------------------------------------------------------------
    # Search & Fetch Settings
    # ------------------------------------------------------------------
    # "searxng_base_url": "http://localhost:8080",
    "max_docs": 16,                      # stop after fetching N documents
    "max_depth": 2,                      # crawl depth for linked pages
    "fetch_timeout": 20.0,               # seconds per HTTP request
    "fetch_concurrency": 3,             # max parallel fetches
    "search_concurrency": 3,             # max parallel SearxNG queries
    "browser_wait_ms": 2000,             # ms to wait after page load (Playwright)
    "enable_browser": True,              # fallback to headless browser?
    "enable_pdf_extraction": True,       # extract text from PDFs via pymupdf?
    "min_content_length": 500,           # min HTML length before browser fallback

    # ------------------------------------------------------------------
    # Critic / Gap Analysis
    # ------------------------------------------------------------------
    "critique_batch_size": 3,            # run critic every N documents

    # ------------------------------------------------------------------
    # Synthesizer / Indexer
    # ------------------------------------------------------------------
    "max_tokens": 16384,                 # LLM output token limit
    "synthesizer_max_tokens": 100_000,   # report section token limit
    "max_indexer_depth": 2,              # max topic hierarchy depth
    "indexer_batch_size": 5,             # documents per indexer LLM call
    "min_accumulator_threshold": 600,  # token threshold before flushing report
    "indexes_dir": "INDEXES",            # on-disk topic tree folder
    "workspace_dir": "workspace",        # scratch pad + final report folder

    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    # "log_level": "INFO",                 # DEBUG | INFO | WARNING | ERROR
}


_START_TIME: float = 0.0


def _elapsed() -> str:
    """Return elapsed time since start as HH:MM:SS."""
    secs = int(time.perf_counter() - _START_TIME)
    return f"{secs // 3600:02d}:{(secs % 3600) // 60:02d}:{secs % 60:02d}"


def _draw_bar(current: int, total: int, width: int = 30) -> str:
    """Return an ASCII progress bar."""
    if total <= 0:
        return ""
    filled = int(width * current / total)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {current}/{total}"


# Mutable state for synthesis progress (simple, module-level)
_synth_state: dict = {
    "total_topics": 0,
    "topics_processed": 0,
    "sections_written": 0,
    "last_bar_line": "",
}


def progress_callback(event_type: str, data: dict) -> None:
    """Print live progress with timestamps."""
    ts = _elapsed()
    match event_type:
        case "status":
            print(f"\n[{ts}] [{data.get('phase', '???').upper()}] {data.get('message', '')}")
        case "plan":
            print(f"\n[{ts}] [PLAN] {len(data.get('queries', []))} search queries generated.")
            for i, q in enumerate(data.get('queries', []), 1):
                print(f"  {i}. {q}")
        case "search":
            print(f"[{ts}]   Search #{data.get('query_index')} returned {data.get('results_count')} results")
        case "document":
            phase = data.get("phase", "???")
            if phase == "fetching":
                print(f"[{ts}]   Fetching {data.get('url', '???')} ...")
            elif phase == "extracted":
                print(f"[{ts}]   ✓ Extracted: {data.get('title', '???')} ({data.get('docs_fetched')}/{data.get('max_docs')})")
        case "gaps":
            print(f"[{ts}]   Gaps found – missing: {len(data.get('missing', []))}, follow-ups: {len(data.get('followup_queries', []))}")
        case "warning":
            print(f"[{ts}]   ⚠ WARNING: {data.get('message', '')}")
        case "complete":
            print(f"\n[{ts}] [DONE] Report complete – {data.get('docs_count')} docs, {data.get('report_length')} chars")

        # ---- Synthesis progress events ----
        case "synth_indexer_batch":
            cur = data.get("current_batch", 0)
            tot = data.get("total_batches", 0)
            print(f"[{ts}]   📚 Indexing batch {cur}/{tot}...")
        case "synth_indexer_complete":
            print(f"[{ts}]   📚 Indexing complete — {data.get('topics_count', '?')} topics.")
        case "synth_overview":
            print(f"[{ts}]   🗺️  {data.get('message', '')}")
        case "synth_report_start":
            _synth_state["total_topics"] = data.get("total_topics", 0)
            _synth_state["topics_processed"] = 0
            _synth_state["sections_written"] = 0
            _synth_state["last_bar_line"] = ""
            print(f"\n[{ts}]   📝 {data.get('message', 'Starting report...')}")
        case "synth_report_section":
            _synth_state["topics_processed"] = data.get("topics_processed", 0)
            _synth_state["sections_written"] = data.get("section_number", 0)
            total = _synth_state["total_topics"] or 1
            current = _synth_state["topics_processed"]
            bar = _draw_bar(current, total)
            title = data.get("section_title", "")
            line = f"[{ts}]   📝 {bar} — Section #{data.get('section_number', '?')}: {title[:50]}"
            # Clear previous bar and rewrite
            print(f"\r{line:<120}", end="", flush=True)
            _synth_state["last_bar_line"] = line
        case "synth_report_complete":
            # Clear the bar line and print completion
            print()
            print(f"[{ts}]   📝 Report writing complete — {data.get('sections_written', '?')} sections.")
        case _:
            pass  # ignore unknown events


async def test_small() -> str:
    global _START_TIME
    _START_TIME = time.perf_counter()

    print("=" * 60)
    print("DeepSearch Caller")
    print("=" * 60)

    query = (
        "Create me a detailed in-depth research-parper on How to build a complete Ai coding harness , out of the box ideas that never has been tried since now..."
    )

    result = await deep_search(
        query,
        config=CUSTOM_CONFIG,
        progress_callback=progress_callback,
    )

    total = _elapsed()

    # Persist result
    out_dir = Path("outputs")
    out_dir.mkdir(exist_ok=True)
    out_file = out_dir / "Buildng_AI_Coding_Harness_v3.md"
    out_file.write_text(result, encoding="utf-8")
    print(f"\n📄 Report saved to: {out_file.resolve()}")
    print(f"⏱️  Total time: {total}")

    return result


if __name__ == "__main__":
    asyncio.run(test_small())
