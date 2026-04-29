from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    engine: str = ""
    score: float = 0.0


@dataclass
class Document:
    url: str
    canonical_url: str
    title: str = ""
    text: str = ""
    author: str = ""
    published_at: str = ""
    language: str = "unknown"
    fetch_mode: str = "http"
    html: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


@dataclass
class FrontierItem:
    url: str
    canonical_url: str
    priority: float
    depth: int = 0
    source_query: str = ""
    domain: str = ""
    status: str = "pending"
    retries: int = 0


@dataclass
class ResearchPlan:
    topic: str
    subquestions: list[str]
    queries: list[str]
    source_preferences: list[str] = field(default_factory=list)
    stop_conditions: dict[str, object] = field(
        default_factory=lambda: {"max_docs": 100, "coverage_threshold": 0.8}
    )


@dataclass
class GapReport:
    covered_subtopics: list[str]
    missing_subtopics: list[str]
    contradictions: list[str]
    followup_queries: list[str]
    should_research_more: bool
