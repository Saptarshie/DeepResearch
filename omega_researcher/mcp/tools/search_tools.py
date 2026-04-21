"""Search tools — SearxNG on-demand + search_from_indexes."""
from __future__ import annotations
from omega_researcher.config import Config
from omega_researcher.search.index_search import IndexSearch


class SearchTools:
    def __init__(self, config: Config, index_manager=None):
        self.config = config
        self.index_manager = index_manager
        self._index_search = IndexSearch(config)

    def searxng_search(self, query: str, categories: str = "general", max_results: int = 10) -> str:
        """On-demand SearxNG search (supplement to main deep_search loop)."""
        try:
            from deepresearch.searx_client import SearxClient
            client = SearxClient(self.config.searxng_base_url)
            results = client.search(query, categories=categories)
            lines = [f"## SearxNG: {query}\n"]
            for i, r in enumerate(results[:max_results], 1):
                lines.append(f"### [{i}] {r.title}\n{r.url}\n{r.snippet}\n")
            return "\n".join(lines)
        except Exception as e:
            return f"[searxng_search error] {e}"

    def search_indexes(self, query: str) -> str:
        """Search INDEXES/ knowledge tree for previously indexed content."""
        return self._index_search.search_formatted(query)

    def list_topics(self) -> str:
        """List all indexed topics."""
        if self.index_manager:
            topics = self.index_manager.list_topics()
        else:
            topics = self._index_search.indexes_dir.rglob("information.md")
            topics = [str(p.parent.relative_to(self._index_search.indexes_dir)) for p in topics]

        if not topics:
            return "No topics indexed yet."
        return "## Indexed Topics\n" + "\n".join(f"- {t}" for t in sorted(topics))
