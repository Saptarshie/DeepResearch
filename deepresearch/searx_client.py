from __future__ import annotations
from typing import Any
import httpx
from deepresearch.schemas import SearchResult


class SearxClient:
    def __init__(self, base_url: str, timeout: int = 30):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.AsyncClient(timeout=timeout)

    async def search(
        self, query: str, language: str = "en", categories: str = "general"
    ) -> list[SearchResult]:
        url = f"{self.base_url}/search"
        params = {
            "q": query,
            "format": "json",
            "language": language,
            "categories": categories,
        }
        r = await self._client.get(url, params=params)
        r.raise_for_status()
        data: dict[str, Any] = r.json()
        results: list[SearchResult] = []
        for item in data.get("results", []):
            results.append(
                SearchResult(
                    title=item.get("title", ""),
                    url=item.get("url", ""),
                    snippet=item.get("content", "") or "",
                    engine=",".join(item.get("engines", []))
                    if isinstance(item.get("engines"), list)
                    else "",
                    score=0.0,
                )
            )
        return results

    async def close(self) -> None:
        await self._client.aclose()
