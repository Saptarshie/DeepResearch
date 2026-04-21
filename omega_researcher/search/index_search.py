"""search_from_indexes() — keyword search over the INDEXES/ knowledge tree."""
from __future__ import annotations
from pathlib import Path
from omega_researcher.config import Config


class IndexSearch:
    """
    Searches the INDEXES/ directory tree for content matching a query.

    Strategy:
    1. Scan all information.md + overview.md files
    2. Simple keyword + sliding-window density ranking
    3. Return top-K matching chunks with source paths
    """

    def __init__(self, config: Config):
        self.indexes_dir = Path(config.indexes_dir)
        self.top_k = config.index_search_top_k

    def search(self, query: str) -> list[dict]:
        """
        Returns list of {path, snippet, score, full_path}
        sorted by relevance descending.
        """
        if not self.indexes_dir.exists():
            return []

        query_words = set(query.lower().split())
        results = []

        for md_file in self.indexes_dir.rglob("*.md"):
            try:
                text = md_file.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            text_lower = text.lower()
            score = sum(text_lower.count(w) for w in query_words)

            if score > 0:
                snippet = _best_snippet(text, query_words, 300)
                results.append({
                    "path": str(md_file.relative_to(self.indexes_dir)),
                    "snippet": snippet,
                    "score": score,
                    "full_path": str(md_file),
                })

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[: self.top_k]

    def search_formatted(self, query: str) -> str:
        """MCP-friendly string output."""
        hits = self.search(query)
        if not hits:
            return "No relevant indexed content found."
        lines = [f"## Indexed Results for: {query}\n"]
        for i, h in enumerate(hits, 1):
            lines.append(f"### [{i}] {h['path']} (score: {h['score']})\n{h['snippet']}\n")
        return "\n".join(lines)


def _best_snippet(text: str, query_words: set, length: int) -> str:
    """Find the window of `length` chars with highest query word density."""
    if len(text) <= length:
        return text.strip()

    best_pos, best_score = 0, 0
    text_lower = text.lower()
    step = max(50, length // 6)

    for i in range(0, len(text) - length, step):
        window = text_lower[i: i + length]
        score = sum(window.count(w) for w in query_words)
        if score > best_score:
            best_score, best_pos = score, i

    return text[best_pos: best_pos + length].strip()
