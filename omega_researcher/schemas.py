"""OmegaResearcher Schemas — all dataclasses and types."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum


# ─── Existing (preserved from deepresearch) ───────────────────────────────────

@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str = ""
    engine: str = ""
    score: float = 0.0


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


# ─── New: Document Ingestion ──────────────────────────────────────────────────

class DocumentSource(Enum):
    WEB       = "web"
    FILE      = "file"
    DATA      = "data"
    SUBAGENT  = "subagent"


@dataclass
class IngestedDocument:
    """Unified document produced by any ingestion path."""
    source_type: DocumentSource
    source_path: str
    title: str
    text: str
    tables: list[dict]        = field(default_factory=list)
    images_desc: list[str]    = field(default_factory=list)
    metadata: dict            = field(default_factory=dict)
    raw_chunks: list[str]     = field(default_factory=list)


# ─── New: Skills ─────────────────────────────────────────────────────────────

@dataclass
class Skill:
    name: str
    description: str
    path: str
    content: str
    tags: list[str]     = field(default_factory=list)
    version: str        = "1.0"


# ─── Research Plan (extended) ────────────────────────────────────────────────

@dataclass
class ResearchPlan:
    topic: str
    subquestions: list[str]
    queries: list[str]
    source_preferences: list[str] = field(default_factory=list)
    stop_conditions: dict         = field(default_factory=dict)
    # New fields for OmegaResearcher
    spawn_subagents: bool         = False
    subagent_topics: list[str]    = field(default_factory=list)
    required_tools: list[str]     = field(default_factory=list)
    active_skills: list[Skill]    = field(default_factory=list)


# ─── Research State ──────────────────────────────────────────────────────────

@dataclass
class ResearchState:
    """Mutable shared state across PAC cycles."""
    query: str
    plan: ResearchPlan
    docs: list[IngestedDocument]        = field(default_factory=list)
    topics_json: dict                   = field(default_factory=dict)
    scratch_pad: str                    = ""
    rolling_summary: str                = ""
    pac_cycle: int                      = 0
    coverage_scores: dict[str, float]   = field(default_factory=dict)
    spawned_subagent_ids: list[str]     = field(default_factory=list)
    active_skills: list[Skill]          = field(default_factory=list)
    depth: int                          = 0


# ─── Action Result ───────────────────────────────────────────────────────────

@dataclass
class ActionResult:
    action_type: str
    success: bool
    output: Any
    error: Optional[str]   = None
    tokens_used: int       = 0
    duration_ms: int       = 0


# ─── Sub-Agent ───────────────────────────────────────────────────────────────

@dataclass
class SubAgentTask:
    task_id: str
    subtopic: str
    parent_depth: int
    config_overrides: dict = field(default_factory=dict)


@dataclass
class SubAgentResult:
    task_id: str
    subtopic: str
    docs: list[IngestedDocument]
    topics_json: dict
    scratch_pad: str
    report_section: str
    success: bool
    error: Optional[str] = None


# ─── Coverage ────────────────────────────────────────────────────────────────

@dataclass
class CoverageReport:
    """Extended GapReport with per-subquestion scores."""
    covered_subtopics: list[str]
    missing_subtopics: list[str]
    contradictions: list[str]
    followup_queries: list[str]
    should_research_more: bool
    coverage_scores: dict[str, float]   = field(default_factory=dict)
    overall_coverage: float             = 0.0
    recommended_actions: list[str]      = field(default_factory=list)


# ─── Experiences ─────────────────────────────────────────────────────────────

@dataclass
class Experience:
    timestamp: str
    query: str
    outcome: str
    coverage_achieved: float
    skills_used: list[str]
    tools_used: list[str]
    what_worked: str
    what_failed: str
    suggestions: str
    subagents_spawned: int
    total_docs: int
    duration_seconds: float
