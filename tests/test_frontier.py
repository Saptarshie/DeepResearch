from __future__ import annotations

from deepresearch.frontier import CrawlFrontier
from deepresearch.schemas import FrontierItem


async def test_frontier_respects_max_depth() -> None:
    frontier = CrawlFrontier(max_depth=2)
    await frontier.push(FrontierItem(
        url="http://a.com", canonical_url="http://a.com", priority=1.0, depth=0,
    ))
    await frontier.push(FrontierItem(
        url="http://b.com", canonical_url="http://b.com", priority=1.0, depth=2,
    ))
    await frontier.push(FrontierItem(
        url="http://c.com", canonical_url="http://c.com", priority=1.0, depth=3,
    ))
    assert frontier.size() == 2


async def test_frontier_allows_exact_max_depth() -> None:
    frontier = CrawlFrontier(max_depth=2)
    await frontier.push(FrontierItem(
        url="http://a.com", canonical_url="http://a.com", priority=1.0, depth=2,
    ))
    assert frontier.size() == 1


async def test_frontier_rejects_negative_depth() -> None:
    frontier = CrawlFrontier(max_depth=-1)
    await frontier.push(FrontierItem(
        url="http://a.com", canonical_url="http://a.com", priority=1.0, depth=0,
    ))
    assert frontier.size() == 0


async def test_frontier_pop_returns_highest_priority() -> None:
    frontier = CrawlFrontier(max_depth=2)
    await frontier.push(FrontierItem(
        url="http://low.com", canonical_url="http://low.com", priority=1.0, depth=0,
    ))
    await frontier.push(FrontierItem(
        url="http://high.com", canonical_url="http://high.com", priority=5.0, depth=0,
    ))
    item = await frontier.pop()
    assert item is not None
    assert item.url == "http://high.com"


async def test_frontier_pop_empty_returns_none() -> None:
    frontier = CrawlFrontier(max_depth=2)
    item = await frontier.pop()
    assert item is None
