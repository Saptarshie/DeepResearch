from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from deepresearch.schemas import FrontierItem


def domain_of(url: str) -> str:
    return urlparse(url).netloc.lower()


class CrawlFrontier:
    def __init__(self, max_depth: int = 2):
        self.q: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._counter = 0
        self.seen: set[str] = set()
        self.max_depth = max_depth

    async def push(self, item: FrontierItem) -> None:
        if not item.canonical_url or item.canonical_url in self.seen:
            return
        if item.depth > self.max_depth:
            return
        self.seen.add(item.canonical_url)
        self._counter += 1
        await self.q.put((-item.priority, self._counter, item))

    async def pop(self) -> FrontierItem | None:
        if self.q.empty():
            return None
        _, _, item = await self.q.get()
        return item

    def empty(self) -> bool:
        return self.q.empty()

    def size(self) -> int:
        """Return the number of items in the queue."""
        return self.q.qsize()
