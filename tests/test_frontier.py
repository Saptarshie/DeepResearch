from __future__ import annotations
import pytest
from deepresearch.frontier import CrawlFrontier
from deepresearch.schemas import FrontierItem


def test_frontier_respects_max_depth() -> None:
    frontier = CrawlFrontier(max_depth=2)
    frontier.push(FrontierItem(url="http://a.com", canonical_url="http://a.com", priority=1.0, depth=0))
    frontier.push(FrontierItem(url="http://b.com", canonical_url="http://b.com", priority=1.0, depth=2))
    frontier.push(FrontierItem(url="http://c.com", canonical_url="http://c.com", priority=1.0, depth=3))
    assert frontier.size() == 2
