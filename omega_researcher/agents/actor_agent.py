"""ActorAgent — executes research actions with INDEX-AS-YOU-GO."""
from __future__ import annotations
import asyncio
from urllib.parse import urlparse
from omega_researcher.schemas import ResearchState, IngestedDocument, DocumentSource

DECIDE_SYSTEM = """You are a research actor. Pick the optimal next action given current state.
Return ONLY valid JSON (no markdown fences):
{
  "type": "web_search",
  "query": "search query here",
  "code": "",
  "subtopics": [],
  "reasoning": "why this action"
}

Valid types: "web_search", "search_indexes", "execute_code", "spawn_subagents", "done"
- Use "web_search" to find new information
- Use "search_indexes" to recall already-indexed knowledge before fetching
- Use "execute_code" when data analysis is needed (only if data files available)
- Use "spawn_subagents" when plan says spawn_subagents=true and depth allows
- Use "done" when no more useful actions remain for this cycle
"""


class ActorAgent:
    """Executes research actions: web crawl, index lookups, code exec, subagent spawning."""

    def __init__(
        self, config, llm, index_manager, scratch_pad, rolling_summary, skill_loader,
        mcp_tools=None,
    ):
        self.config = config
        self.llm = llm
        self.index_manager = index_manager
        self.scratch_pad = scratch_pad
        self.rolling_summary = rolling_summary
        self.skill_loader = skill_loader
        self.mcp_tools = mcp_tools  # dict of callable tools, populated by orchestrator

    async def run_cycle(self, state: ResearchState) -> ResearchState:
        """One PAC cycle: execute up to actor_max_actions_per_cycle actions."""
        for action_num in range(self.config.actor_max_actions_per_cycle):
            action = await self._decide_next_action(state)
            action_type = action.get("type", "done")

            print(f"  [actor] Action {action_num+1}: {action_type} — {action.get('reasoning', '')[:80]}")

            if action_type == "web_search":
                query = action.get("query", state.query)
                new_docs = await self._do_web_search(query, state)
                for doc in new_docs:
                    state.docs.append(doc)
                    result = self.index_manager.index_document(
                        doc, state.query, self.llm, self.scratch_pad.read()
                    )
                    if result.get("scratch_pad_update"):
                        self.scratch_pad.append("Global Notes", result["scratch_pad_update"])
                    state.topics_json = result["topics_json"]

                # Remove used query from plan
                if query in state.plan.queries:
                    state.plan.queries.remove(query)

            elif action_type == "search_indexes":
                query = action.get("query", state.query)
                from omega_researcher.search.index_search import IndexSearch
                searcher = IndexSearch(self.config)
                result = searcher.search_formatted(query)
                self.scratch_pad.append("Index Lookups", f"\n**Query:** {query}\n{result}")

            elif action_type == "execute_code":
                code = action.get("code", "")
                if code and self.mcp_tools and "execute_python" in self.mcp_tools:
                    result = self.mcp_tools["execute_python"](code)
                    self.scratch_pad.append("Code Results", f"\n```python\n{code}\n```\n**Output:**\n{result}")
                else:
                    print("  [actor] execute_code: no docker executor available, skipping")

            elif action_type == "spawn_subagents":
                subtopics = action.get("subtopics", state.plan.subagent_topics)
                if subtopics and state.depth < self.config.SPAWNING_DEPTH_LIMIT:
                    from omega_researcher.agents.subagent_spawner import SubagentSpawner
                    spawner = SubagentSpawner(self.config, self.llm, self.index_manager, self.skill_loader)
                    results = await spawner.spawn_for_subquestions(subtopics, state)
                    state = spawner.merge_results(state, results)
                else:
                    print(f"  [actor] spawn_subagents: depth limit or no topics, skipping")

            elif action_type == "done":
                break

            # Update rolling summary after each action
            self.rolling_summary.update(
                f"Cycle {state.pac_cycle}, action {action_num+1}: {action_type} | "
                f"total docs={len(state.docs)} | topics={len(state.topics_json)}",
                context=state.query,
            )

        return state

    async def _decide_next_action(self, state: ResearchState) -> dict:
        """LLM decides what to do next based on current state."""
        skill_guidance = "\n".join(
            s.content[:400] for s in state.active_skills[:2]
        )

        remaining_queries = state.plan.queries[:3]
        indexed_topics = list(state.topics_json.keys())[:10]

        prompt = f"""Research query: {state.query}
PAC cycle: {state.pac_cycle}
Documents collected: {len(state.docs)}
Current rolling summary: {self.rolling_summary.get()[-500:]}
Scratch pad (recent): {self.scratch_pad.read("Global Notes")[-300:]}
Indexed topics: {indexed_topics}
Remaining queries in plan: {remaining_queries}
Spawn subagents allowed: {state.plan.spawn_subagents and state.depth < self.config.SPAWNING_DEPTH_LIMIT}
Active skills guidance:
{skill_guidance[:400]}

What is the best next action? Return JSON."""

        try:
            return self.llm.json(prompt, system=DECIDE_SYSTEM, use_claude=True, max_tokens=1000)
        except Exception as e:
            print(f"  [actor] _decide_next_action failed: {e}, defaulting to web_search")
            remaining = state.plan.queries
            return {
                "type": "web_search" if remaining else "done",
                "query": remaining[0] if remaining else "",
                "reasoning": "fallback",
            }

    async def _do_web_search(self, query: str, state: ResearchState) -> list[IngestedDocument]:
        """Run the original deep_search crawl loop for one query."""
        from deepresearch.searx_client import SearxClient
        from deepresearch.frontier import CrawlFrontier, domain_of
        from deepresearch.fetcher import PageFetcher
        from deepresearch.extractor import extract_document
        from deepresearch.schemas import FrontierItem

        results = []
        try:
            searx = SearxClient(self.config.searxng_base_url)
            search_results = searx.search(query)
        except Exception as e:
            print(f"  [actor] SearxNG search failed: {e}")
            return []

        frontier = CrawlFrontier()
        for r in search_results:
            score = _score_result(r.title, r.url, r.snippet)
            frontier.push(FrontierItem(
                url=r.url,
                canonical_url=r.url,
                priority=score,
                source_query=query,
                domain=domain_of(r.url),
            ))

        fetcher = PageFetcher(timeout=self.config.fetch_timeout, max_retries=2)
        max_per_query = min(10, self.config.max_docs - len(state.docs))

        while not frontier.empty() and len(results) < max_per_query:
            item = frontier.pop()
            if not item:
                break
            try:
                fetch_res = await fetcher.fetch(item.url)
                extracted = extract_document(fetch_res.html, fetch_res.final_url)
                if len(extracted.get("text", "")) > 200:
                    doc = IngestedDocument(
                        source_type=DocumentSource.WEB,
                        source_path=fetch_res.final_url,
                        title=extracted.get("title", item.url),
                        text=extracted.get("text", ""),
                        metadata={
                            "author": extracted.get("author", ""),
                            "published_at": extracted.get("published_at", ""),
                            "url": fetch_res.final_url,
                        },
                    )
                    results.append(doc)
            except Exception:
                pass

        return results


def _score_result(title: str, url: str, snippet: str) -> float:
    score = 1.0
    title_l = title.lower()
    if any(k in title_l for k in ["research", "paper", "docs", "official", "report", "study"]):
        score += 1.5
    if url.endswith(".pdf"):
        score += 1.0
    if len(snippet) > 80:
        score += 0.2
    return score
