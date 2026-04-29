from __future__ import annotations
import asyncio
from urllib.parse import urlparse
from typing import Callable, Any
from deepresearch.config import Config
from deepresearch.llm_client import LLMClient
from deepresearch.searx_client import SearxClient
from deepresearch.frontier import CrawlFrontier, domain_of
from deepresearch.fetcher import PageFetcher
from deepresearch.extractor import extract_document
from deepresearch.planner import Planner
from deepresearch.critic import Critic
from deepresearch.synthesizer import Synthesizer
from deepresearch.schemas import FrontierItem


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


async def deep_search(
    query: str,
    config: Config | dict | None = None,
    progress_callback: Callable[[str, dict[str, Any]], None] | None = None
) -> str:
    """
    Perform deep research on a query.
    
    Args:
        query: The research query
        config: Configuration object or dict with config options
        progress_callback: Optional callback function(event_type, data) for progress updates
            Event types: 'status', 'search', 'document', 'synthesizing', 'complete'
    
    Returns:
        Markdown report string
    """
    if config is None:
        cfg = Config()
    elif isinstance(config, dict):
        cfg = Config(**config)
    else:
        cfg = config
    
    def emit(event_type: str, data: dict[str, Any] = None):
        if progress_callback:
            progress_callback(event_type, data or {})
    
    emit("status", {"phase": "initializing", "message": "Setting up research pipeline..."})
    
    llm = LLMClient(cfg)
    fetcher = PageFetcher(timeout=cfg.fetch_timeout, max_retries=3)
    planner = Planner(llm)
    critic = Critic(llm)
    synthesizer = Synthesizer(llm)
    
    async with SearxClient(cfg.searxng_base_url) as searx:
        emit("status", {"phase": "planning", "message": "Creating research plan..."})
        plan = planner.make_plan(query)
        emit("plan", {"queries": plan.queries, "subquestions": plan.subquestions})
        
        frontier = CrawlFrontier()
        docs: list[dict] = []
        
        emit("status", {"phase": "searching", "message": "Searching for relevant sources..."})
        for i, q in enumerate(plan.queries):
            try:
                results = await searx.search(q)
                emit("search", {"query": q, "results_count": len(results), "query_index": i + 1, "total_queries": len(plan.queries)})
                for r in results:
                    if not r.url:
                        continue
                    item = FrontierItem(
                        url=r.url,
                        canonical_url=r.url.split("#")[0],
                        priority=score_result(r.title, r.url, r.snippet),
                        source_query=q,
                        domain=domain_of(r.url),
                    )
                    frontier.push(item)
            except Exception as e:
                print(f"[warn] search failed for '{q}': {e}")
                emit("warning", {"message": f"Search failed for '{q}': {e}"})
        
        total_urls = frontier.size()
        emit("status", {"phase": "fetching", "message": f"Fetching documents...", "total_urls": total_urls})
        
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
                doc = {
                    "url": fetched.url,
                    "final_url": fetched.final_url,
                    "fetch_mode": fetched.fetch_mode,
                    "status_code": fetched.status_code,
                    **extracted,
                }
                docs.append(doc)
                
                emit("document", {
                    "url": item.url,
                    "title": extracted.get("title", ""),
                    "docs_fetched": len(docs),
                    "max_docs": cfg.max_docs,
                    "phase": "extracted"
                })
                
                if len(docs) % cfg.critique_batch_size == 0:
                    emit("status", {"phase": "critiquing", "message": f"Analyzing gaps in research ({len(docs)} documents)..."})
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
                                    if r.url:
                                        frontier.push(
                                            FrontierItem(
                                                url=r.url,
                                                canonical_url=r.url.split("#")[0],
                                                priority=score_result(
                                                    r.title, r.url, r.snippet
                                                )
                                                + 0.5,
                                                source_query=q,
                                                domain=domain_of(r.url),
                                            )
                                        )
                            except Exception as e:
                                print(f"[warn] re-search failed for '{q}': {e}")
                                emit("warning", {"message": f"Re-search failed for '{q}': {e}"})
            except Exception as e:
                print(f"[warn] fetch failed for {item.url}: {e}")
                emit("warning", {"message": f"Fetch failed for {item.url}: {e}"})
        
        emit("status", {"phase": "synthesizing", "message": f"Synthesizing report from {len(docs)} documents..."})
        result = synthesizer.synthesize(query, docs)
        emit("complete", {"docs_count": len(docs), "report_length": len(result)})
        
        return result