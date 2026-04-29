from __future__ import annotations

from deepresearch.frontier import CrawlFrontier
from deepresearch.schemas import FrontierItem


def test_frontier_respects_max_depth() -> None:
    frontier = CrawlFrontier(max_depth=2)
    frontier.push(FrontierItem(
        url="http://a.com", canonical_url="http://a.com", priority=1.0, depth=0,
    ))
    frontier.push(FrontierItem(
        url="http://b.com", canonical_url="http://b.com", priority=1.0, depth=2,
    ))
    frontier.push(FrontierItem(
        url="http://c.com", canonical_url="http://c.com", priority=1.0, depth=3,
    ))
    assert frontier.size() == 2


def test_frontier_allows_exact_max_depth() -> None:
    frontier = CrawlFrontier(max_depth=2)
    frontier.push(FrontierItem(
        url="http://a.com", canonical_url="http://a.com", priority=1.0, depth=2,
    ))
    assert frontier.size() == 1


def test_frontier_rejects_negative_depth() -> None:
    frontier = CrawlFrontier(max_depth=-1)
    frontier.push(FrontierItem(
        url="http://a.com", canonical_url="http://a.com", priority=1.0, depth=0,
    ))
    assert frontier.size() == 0
