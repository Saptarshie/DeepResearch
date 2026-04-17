from __future__ import annotations
import asyncio
from urllib.parse import urlparse
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
async def deep_search(query: str, config: Config | dict | None = None) -> str:
    if config is None:
        cfg = Config()
    elif isinstance(config, dict):
        cfg = Config(**config)
    else:
        cfg = config
    llm = LLMClient(cfg)
    searx = SearxClient(cfg.searxng_base_url)
    fetcher = PageFetcher(timeout=cfg.fetch_timeout, max_retries=3)
    planner = Planner(llm)
    critic = Critic(llm)
    synthesizer = Synthesizer(llm)
    plan = planner.make_plan(query)
    frontier = CrawlFrontier()
    docs: list[dict] = []
    for q in plan.queries:
        try:
            results = searx.search(q)
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
    while not frontier.empty() and len(docs) < cfg.max_docs:
        item = frontier.pop()
        if not item:
            break
        try:
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
            if len(docs) % cfg.critique_batch_size == 0:
                gap_report = critic.find_gaps(query, docs)
                if gap_report.should_research_more:
                    for q in gap_report.followup_queries:
                        try:
                            extra = searx.search(q)
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
        except Exception as e:
            print(f"[warn] fetch failed for {item.url}: {e}")
    return synthesizer.synthesize(query, docs)