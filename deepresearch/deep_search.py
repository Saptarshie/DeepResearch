from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Callable
from typing import Any

from deepresearch.config import Config
from deepresearch.critic import Critic
from deepresearch.extractor import extract_document
from deepresearch.fetcher import PageFetcher
from deepresearch.frontier import CrawlFrontier, domain_of
from deepresearch.llm_client import LLMClient
from deepresearch.planner import Planner
from deepresearch.schemas import FrontierItem
from deepresearch.searx_client import SearxClient
from deepresearch.synthesizer import Synthesizer
from deepresearch.url_validator import is_safe_url

logger = logging.getLogger(__name__)


def score_result(title: str, url: str, snippet: str) -> float:
    score = 1.0
    if any(
        k in title.lower() for k in ["research", "paper", "docs", "official", "report"]
    ):
        score += 1.5
    if url.endswith(".pdf"):
        score += 1.0
    if len(snippet) > 80:
        score += 0.2
    return score


def _normalize_text(text: str) -> str:
    return " ".join(text.lower().split())


async def deep_search(
    query: str,
    config: Config | dict | None = None,
    progress_callback: Callable[[str, dict[str, Any]], None] | None = None
) -> str:
    if config is None:
        cfg = Config()
    elif isinstance(config, dict):
        cfg = Config(**config)
    else:
        cfg = config

    def emit(event_type: str, data: dict[str, Any] | None = None):
        if progress_callback:
            progress_callback(event_type, data or {})

    emit("status", {"phase": "initializing", "message": "Setting up research pipeline..."})

    llm = LLMClient(cfg)
    searx = SearxClient(cfg.searxng_base_url)
    fetcher = PageFetcher(
        timeout=cfg.fetch_timeout,
        max_retries=3,
        browser_wait_ms=cfg.browser_wait_ms,
        enable_browser=cfg.enable_browser,
    )
    planner = Planner(llm)
    critic = Critic(llm)
    synthesizer = Synthesizer(llm, cfg)

    emit("status", {"phase": "planning", "message": "Creating research plan..."})
    plan = planner.make_plan(query)
    emit("plan", {"queries": plan.queries, "subquestions": plan.subquestions})

    frontier = CrawlFrontier(max_depth=cfg.max_depth)
    docs: list[dict] = []
    seen_content_hashes: set[str] = set()

    emit("status", {"phase": "searching", "message": "Searching for relevant sources..."})

    async def _search_one(q: str) -> list:
        try:
            return await searx.search(q)
        except Exception as e:
            logger.warning("Search failed for '%s': %s", q, e)
            emit("warning", {"message": f"Search failed for '{q}': {e}"})
            return []

    search_results = await asyncio.gather(*[_search_one(q) for q in plan.queries])
    for i, results in enumerate(search_results):
        emit("search", {
            "query": plan.queries[i],
            "results_count": len(results),
            "query_index": i + 1,
            "total_queries": len(plan.queries),
        })
        for r in results:
            if not r.url:
                continue
            if not is_safe_url(r.url):
                logger.warning("Blocked unsafe URL: %s", r.url)
                continue
            item = FrontierItem(
                url=r.url,
                canonical_url=r.url.split("#")[0],
                priority=score_result(r.title, r.url, r.snippet),
                source_query=plan.queries[i],
                domain=domain_of(r.url),
            )
            frontier.push(item)

    total_urls = frontier.size()
    emit("status", {
        "phase": "fetching",
        "message": "Fetching documents...",
        "total_urls": total_urls,
    })

    try:
        while not frontier.empty() and len(docs) < cfg.max_docs:
            item = frontier.pop()
            if not item:
                break
            try:
                emit("document", {
                    "url": item.url,
                    "docs_fetched": len(docs) + 1,
                    "max_docs": cfg.max_docs,
                    "phase": "fetching"
                })
                fetched = await fetcher.fetch(item.url)
                extracted = extract_document(fetched.html, fetched.final_url)
                normalized = _normalize_text(extracted.text)
                content_hash = hashlib.md5(normalized.encode()).hexdigest()
                if content_hash in seen_content_hashes:
                    logger.info("Skipping duplicate content: %s", item.url)
                    continue
                seen_content_hashes.add(content_hash)
                doc = {
                    "url": fetched.url,
                    "final_url": fetched.final_url,
                    "fetch_mode": fetched.fetch_mode,
                    "status_code": fetched.status_code,
                    "title": extracted.title,
                    "text": extracted.text,
                    "author": extracted.author,
                    "published_at": extracted.published_at,
                    "language": extracted.language,
                    "metadata": extracted.metadata,
                }
                docs.append(doc)
                emit("document", {
                    "url": item.url,
                    "title": extracted.title,
                    "docs_fetched": len(docs),
                    "max_docs": cfg.max_docs,
                    "phase": "extracted"
                })
                if len(docs) % cfg.critique_batch_size == 0:
                    emit("status", {
                        "phase": "critiquing",
                        "message": f"Analyzing gaps ({len(docs)} documents)...",
                    })
                    gap_report = critic.find_gaps(query, docs)
                    if gap_report.should_research_more:
                        emit("gaps", {
                            "covered": gap_report.covered_subtopics,
                            "missing": gap_report.missing_subtopics,
                            "followup_queries": gap_report.followup_queries
                        })
                        for q in gap_report.followup_queries:
                            try:
                                extra = await searx.search(q)
                                for r in extra:
                                    if r.url and is_safe_url(r.url):
                                        frontier.push(
                                            FrontierItem(
                                                url=r.url,
                                                canonical_url=r.url.split("#")[0],
                                                priority=(
                                                    score_result(r.title, r.url, r.snippet) + 0.5
                                                ),
                                                source_query=q,
                                                domain=domain_of(r.url),
                                            )
                                        )
                            except Exception as e:
                                logger.warning("Re-search failed for '%s': %s", q, e)
                                emit("warning", {"message": f"Re-search failed for '{q}': {e}"})
            except Exception as e:
                logger.warning("Fetch failed for %s: %s", item.url, e)
                emit("warning", {"message": f"Fetch failed for {item.url}: {e}"})
    finally:
        try:
            await fetcher.close()
        except Exception:
            logger.warning("Error closing fetcher", exc_info=True)
        try:
            await searx.close()
        except Exception:
            logger.warning("Error closing searx client", exc_info=True)

    emit("status", {
        "phase": "synthesizing",
        "message": f"Synthesizing report from {len(docs)} documents...",
    })
    result = synthesizer.synthesize(query, docs)
    emit("complete", {"docs_count": len(docs), "report_length": len(result)})
    return result
