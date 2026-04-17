from __future__ import annotations
from queue import PriorityQueue
from urllib.parse import urlparse
from deepresearch.schemas import FrontierItem


def domain_of(url: str) -> str:
    return urlparse(url).netloc.lower()


class CrawlFrontier:
    def __init__(self):
        self.q: PriorityQueue = PriorityQueue()
        self._counter = 0
        self.seen: set[str] = set()

    def push(self, item: FrontierItem):
        if not item.canonical_url or item.canonical_url in self.seen:
            return
        self.seen.add(item.canonical_url)
        self._counter += 1
        self.q.put((-item.priority, self._counter, item))

    def pop(self) -> FrontierItem | None:
        if self.q.empty():
            return None
        _, _, item = self.q.get()
        return item

    def empty(self) -> bool:
        return self.q.empty()
