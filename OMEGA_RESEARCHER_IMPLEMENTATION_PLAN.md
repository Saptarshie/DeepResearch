# OmegaResearcher — Complete Implementation Plan

> **Transforming `deepresearch` from a report-writer into a full autonomous research intelligence system.**

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Architecture Overview](#2-architecture-overview)
3. [Full Project Structure](#3-full-project-structure)
4. [Configuration (`config.py`)](#4-configuration-configpy)
5. [Schemas (`schemas.py`)](#5-schemas-schemaspy)
6. [Document Ingestion (Docling)](#6-document-ingestion-docling)
7. [Memory System](#7-memory-system)
8. [Dynamic Skills System](#8-dynamic-skills-system)
9. [MCP Server & Tools](#9-mcp-server--tools)
10. [Multi-Agent Sub-Spawner](#10-multi-agent-sub-spawner)
11. [Planner–Actor–Critic (PAC) Framework](#11-planneractorcritic-pac-framework)
12. [Experiences & MetaLearn](#12-experiences--metalearnsystem)
13. [Enhanced Synthesizer](#13-enhanced-synthesizer)
14. [LLM Client (enhanced)](#14-llm-client-enhanced)
15. [Integration: Full Data Flow](#15-integration-full-data-flow)
16. [Docker & Infrastructure](#16-docker--infrastructure)
17. [Configuration Reference](#17-configuration-reference)
18. [Implementation Roadmap (Phases)](#18-implementation-roadmap-phases)
19. [File-by-File Implementation Guide](#19-file-by-file-implementation-guide)

---

## 1. Executive Summary

### What exists today

| Component | File | Status |
|---|---|---|
| Research planner | `planner.py` | ✅ Works |
| SearxNG search | `searx_client.py` | ✅ Works |
| Web fetcher (HTTP+Playwright) | `fetcher.py` | ✅ Works |
| HTML extractor (trafilatura) | `extractor.py` | ✅ Works |
| Critic / gap analysis | `critic.py` | ✅ Works |
| Frontier queue | `frontier.py` | ✅ Works |
| INDEX-AS-YOU-GO | `synthesizer/indexer.py` | ✅ Works |
| Overview builder | `synthesizer/overview_builder.py` | ✅ Works |
| Report builder | `synthesizer/report_builder.py` | ✅ Works |
| scratch_pad.md | (written by indexer) | ✅ Works (basic) |
| Rolling summary | (inside report_builder only) | ⚠️ Partial |
| Dual LLM (MiniMax + Claude) | `llm_client.py` | ✅ Works |

### What will be added

| Feature | New Module | Priority |
|---|---|---|
| Docling document ingestion (PDF/DOCX/PPTX/HTML) | `ingestion/docling_parser.py` | 🔴 High |
| Tabular ingestion (Excel/CSV) with analytics | `ingestion/data_reader.py` | 🔴 High |
| Formal PAC loop orchestrator | `orchestrator.py` | 🔴 High |
| MCP Server with all tools | `mcp/` | 🔴 High |
| Docker Python code executor | `mcp/tools/code_executor.py` | 🔴 High |
| `search_from_indexes()` | `memory/index_search.py` | 🔴 High |
| Proper rolling summary | `memory/rolling_summary.py` | 🔴 High |
| Enhanced scratch pad (shared state) | `memory/scratch_pad.py` | 🟡 Medium |
| Dynamic skill loading | `skills/skill_loader.py` | 🟡 Medium |
| `create_skill()` MCP tool | `skills/skill_creator.py` | 🟡 Medium |
| Parallel sub-agent spawner | `agents/subagent_spawner.py` | 🟡 Medium |
| experiences.md + MetaLearn | `memory/experiences.py` + `agents/meta_agent.py` | 🟡 Medium |
| SearxNG on-demand MCP tool | `mcp/tools/search_tools.py` | 🟢 Low |
| Data-reading MCP tools | `mcp/tools/data_tools.py` | 🟢 Low |

---

## 2. Architecture Overview

```
                    ┌─────────────────────────────────────────────────────┐
                    │                  OmegaResearcher                    │
                    │           Planner → Actor → Critic Loop             │
                    └──────────────────────┬──────────────────────────────┘
                                           │
            ┌──────────────────────────────┼──────────────────────────────┐
            │                             │                              │
     ┌──────▼──────┐            ┌─────────▼─────────┐          ┌────────▼───────┐
     │   PLANNER   │            │      ACTOR        │          │    CRITIC      │
     │             │            │                   │          │                │
     │ - load skills│           │ - execute tools   │          │ - gap analysis │
     │ - make plan │            │ - call MCPs       │          │ - post-eval    │
     │ - decide    │            │ - spawn subagents │          │ - coverage     │
     │   subagents │            │ - index as you go │          │   scoring      │
     └─────────────┘            └─────────┬─────────┘          └────────────────┘
                                          │
              ┌───────────────────────────┼───────────────────────────┐
              │                           │                           │
     ┌────────▼────────┐       ┌──────────▼──────────┐    ┌──────────▼──────────┐
     │  MEMORY SYSTEM  │       │    MCP TOOL LAYER   │    │   INGESTION LAYER   │
     │                 │       │                     │    │                     │
     │ • INDEXES/      │       │ • code_executor     │    │ • Docling parser    │
     │ • scratch_pad   │       │ • searxng_search    │    │   PDF/DOCX/PPTX/HTML│
     │ • rolling_summary│      │ • search_indexes    │    │ • data_reader       │
     │ • experiences   │       │ • data_reader       │    │   Excel/CSV         │
     │ • topics.json   │       │ • create_skill      │    │ • web_fetcher       │
     └─────────────────┘       │ • load_skill        │    │   HTTP+Playwright   │
                               └─────────────────────┘    └─────────────────────┘
              │
     ┌────────▼────────────────────────────────────────────────────────────────┐
     │                        SKILLS SYSTEM                                    │
     │  SKILLS/web_scraping/SKILL.md  |  SKILLS/data_analysis/SKILL.md  | ... │
     │  Dynamic loading at runtime based on task type                          │
     └─────────────────────────────────────────────────────────────────────────┘
              │
     ┌────────▼────────────────────────────────────────────────────────────────┐
     │                    SUB-AGENT SPAWNER (depth ≤ 3)                        │
     │  SubAgent[depth=1] spawns SubAgent[depth=2] spawns SubAgent[depth=3]    │
     │  Each runs its own PAC loop. Results merged back to parent context.     │
     └─────────────────────────────────────────────────────────────────────────┘
              │
     ┌────────▼────────────────────────────────────────────────────────────────┐
     │                  META-AGENT (SEPARATE, NO CONTEXT SHARING)              │
     │  Reads experiences.md → triggers MetaLearn() → updates/creates SKILLS   │
     └─────────────────────────────────────────────────────────────────────────┘
```

### Planner–Actor–Critic Loop (Detailed)

```
User Query / Files
       │
  ┌────▼──────────────────────────────────────────┐
  │  PLANNER                                       │
  │  1. load_skills(task_type)                     │
  │  2. decide: spawn_subagents? (yes/no)          │
  │  3. generate research_plan (subquestions,      │
  │     queries, file_paths, data_paths)           │
  │  4. identify tool needs (MCP tools required)   │
  └────┬──────────────────────────────────────────┘
       │ ResearchPlan
  ┌────▼──────────────────────────────────────────┐
  │  ACTOR (main execution loop)                   │
  │                                                │
  │  For each action cycle:                        │
  │   a. pick_next_action() from plan/gaps         │
  │   b. execute via MCP tool OR direct call:      │
  │      - deep_search() [existing searxng loop]   │
  │      - searxng_search() [on-demand]            │
  │      - search_from_indexes() [memory]          │
  │      - ingest_document(path)  [docling]        │
  │      - read_data(path)  [csv/excel]            │
  │      - execute_code(script)  [docker]          │
  │      - spawn_subagent(subtopic)  [recursive]   │
  │   c. INDEX results → INDEXES/ as-you-go        │
  │   d. update scratch_pad + rolling_summary      │
  │   e. emit to Critic every N actions            │
  └────┬──────────────────────────────────────────┘
       │ (docs, index state, rolling_summary)
  ┌────▼──────────────────────────────────────────┐
  │  CRITIC                                        │
  │  1. evaluate coverage vs plan.subquestions     │
  │  2. score each subquestion [0..1]              │
  │  3. return GapReport + CoverageScore           │
  │  4. if coverage < threshold → feed gaps back   │
  │     to ACTOR for next cycle                    │
  │  5. if coverage ≥ threshold OR max_docs hit    │
  │     → signal SYNTHESIZER                       │
  └────┬──────────────────────────────────────────┘
       │ (all indexes, scratch_pad)
  ┌────▼──────────────────────────────────────────┐
  │  SYNTHESIZER                                   │
  │  overview_builder → report_builder → final MD  │
  └────────────────────────────────────────────────┘
       │
  ┌────▼──────────────────────────────────────────┐
  │  META-AGENT (runs in separate LLM context)     │
  │  post_eval(plan, report) → experiences.md      │
  │  MetaLearn() → create/update SKILLS            │
  └────────────────────────────────────────────────┘
```

---

## 3. Full Project Structure

```
omega_researcher/
│
├── config.py                          # All configuration (greatly expanded)
├── schemas.py                         # All dataclasses/types (expanded)
├── orchestrator.py                    # PAC loop top-level entry point
├── main.py                            # CLI + programmatic API entry
│
├── agents/
│   ├── __init__.py
│   ├── base_agent.py                  # BaseAgent: shared state, MCP access, logging
│   ├── planner_agent.py               # PlannerAgent: plan generation with skill loading
│   ├── actor_agent.py                 # ActorAgent: tool execution, indexing, fetching
│   ├── critic_agent.py                # CriticAgent: gap analysis, coverage scoring
│   ├── subagent_spawner.py            # SubagentSpawner: parallel recursive agents
│   └── meta_agent.py                  # MetaAgent: post-eval, experiences, MetaLearn
│
├── ingestion/
│   ├── __init__.py
│   ├── docling_parser.py              # Docling: PDF, DOCX, PPTX, HTML → Document
│   ├── data_reader.py                 # CSV/Excel: head(), describe(), schema(), full read
│   └── web_fetcher.py                 # (moved from fetcher.py, enhanced)
│
├── search/
│   ├── __init__.py
│   ├── searx_client.py                # (from existing, unchanged)
│   ├── deep_search.py                 # (enhanced, now calls actor_agent tools)
│   └── index_search.py               # search_from_indexes() — semantic INDEXES/ lookup
│
├── memory/
│   ├── __init__.py
│   ├── index_manager.py               # Wraps synthesizer/indexer.py with live-access API
│   ├── rolling_summary.py             # RollingSummary: compress context on-the-fly
│   ├── scratch_pad.py                 # ScratchPad: shared mutable state (thread-safe)
│   └── experiences.py                 # ExperienceLogger: write/read experiences.md
│
├── skills/
│   ├── __init__.py
│   ├── skill_loader.py                # Load SKILLS/*/SKILL.md dynamically
│   └── skill_creator.py               # create_skill(): write new SKILL.md files
│
├── mcp/
│   ├── __init__.py
│   ├── mcp_server.py                  # FastMCP server: registers and exposes all tools
│   └── tools/
│       ├── __init__.py
│       ├── code_executor.py           # Docker sandbox: run Python with analytics libs
│       ├── data_tools.py              # head(), summary(), stats(), schema() for files
│       ├── search_tools.py            # searxng_search(), search_from_indexes()
│       ├── file_tools.py              # ingest_document() for Docling files
│       └── skill_tools.py             # create_skill(), load_skill(), list_skills()
│
├── synthesizer/
│   ├── __init__.py
│   ├── synthesizer.py                 # Enhanced synthesizer (uses memory + rolling_summary)
│   ├── indexer.py                     # (from existing, enhanced — INDEX-AS-YOU-GO)
│   ├── overview_builder.py            # (from existing, unchanged)
│   └── report_builder.py             # (from existing, enhanced)
│
├── llm_client.py                      # (from existing, enhanced with tool-call support)
├── extractor.py                       # (from existing, unchanged)
├── frontier.py                        # (from existing, unchanged)
│
├── INDEXES/                           # Auto-managed knowledge tree (gitignored output)
│   └── overview.md
│
├── SKILLS/                            # Skill library (version-controlled)
│   ├── web_scraping/
│   │   └── SKILL.md
│   ├── data_analysis/
│   │   └── SKILL.md
│   ├── academic_research/
│   │   └── SKILL.md
│   ├── code_analysis/
│   │   └── SKILL.md
│   └── financial_research/
│       └── SKILL.md
│
├── scratch_pad.md                     # Live shared scratch pad (overwritten each run)
├── rolling_summary.md                 # Compressed running context
├── experiences.md                     # Success/failure/eval log (append-only)
├── topics.json                        # Current topics hierarchy
│
├── docker/
│   ├── Dockerfile.executor            # Python analytics sandbox image
│   └── docker-compose.yml             # searxng + executor services
│
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## 4. Configuration (`config.py`)

### Full expanded config

```python
# config.py
from __future__ import annotations
import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    # ─── LLM Providers ───────────────────────────────────────────────────
    minimax_api_key: str        = os.getenv("MINIMAX_API_KEY", "")
    minimax_model: str          = os.getenv("MINIMAX_MODEL", "MiniMax-M1")
    anthropic_base_url: str     = os.getenv("ANTHROPIC_BASE_URL", "https://api.minimax.io/anthropic")
    anthropic_api_key: str      = os.getenv("ANTHROPIC_API_KEY", "")
    claude_model: str           = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-20250514")

    # ─── Search ──────────────────────────────────────────────────────────
    searxng_base_url: str       = os.getenv("SEARXNG_BASE_URL", "http://localhost:8080")
    max_docs: int               = 100           # Hard cap on web-crawled docs
    critique_batch_size: int    = 10            # Critic runs every N docs
    fetch_timeout: float        = 20.0
    browser_wait_ms: int        = 2000

    # ─── LLM Token Limits ────────────────────────────────────────────────
    max_tokens: int             = 16384
    synthesizer_max_tokens: int = 100000
    meta_max_tokens: int        = 8192          # MetaAgent uses cheaper model

    # ─── Indexing ────────────────────────────────────────────────────────
    max_indexer_depth: int      = 3
    indexes_dir: str            = "INDEXES"
    skills_dir: str             = "SKILLS"

    # ─── Memory ──────────────────────────────────────────────────────────
    scratch_pad_path: str       = "scratch_pad.md"
    rolling_summary_path: str   = "rolling_summary.md"
    experiences_path: str       = "experiences.md"
    rolling_summary_max_tokens: int = 2000      # Compress when exceeds this
    index_search_top_k: int     = 5             # search_from_indexes() returns top-K

    # ─── Multi-Agent ─────────────────────────────────────────────────────
    SPAWNING_DEPTH_LIMIT: int   = 3             # Max recursive subagent depth
    max_subagents: int          = 5             # Max parallel subagents per node
    subagent_max_docs: int      = 30            # Subagents get smaller budgets
    subagent_timeout: int       = 300           # Seconds before subagent is killed

    # ─── MCP / Code Executor ─────────────────────────────────────────────
    mcp_host: str               = "localhost"
    mcp_port: int               = 8765
    docker_executor_image: str  = "omega-executor:latest"
    docker_executor_timeout: int = 60           # Seconds for code execution
    docker_network: str         = "omega_net"

    # ─── Docling ─────────────────────────────────────────────────────────
    docling_ocr: bool           = True          # Enable OCR for scanned PDFs
    docling_table_mode: str     = "accurate"    # "accurate" | "fast"
    max_file_size_mb: int       = 50            # Skip files larger than this

    # ─── MetaLearn ───────────────────────────────────────────────────────
    metalear_trigger_every: int = 10            # Run MetaLearn every N experiences
    metalear_min_failures: int  = 3             # Min failures before skill update

    # ─── PAC Loop ────────────────────────────────────────────────────────
    coverage_threshold: float   = 0.85          # Critic score to stop loop
    max_pac_cycles: int         = 20            # Safety limit on PAC iterations
    actor_max_actions_per_cycle: int = 5        # Actions before Critic re-runs
```

---

## 5. Schemas (`schemas.py`)

### New dataclasses required

```python
# schemas.py (additions to existing)
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Any
from enum import Enum

# ─── Existing (keep unchanged) ────────────────────────────────────────────────
# SearchResult, Document, FrontierItem, ResearchPlan, GapReport — unchanged

# ─── New: Document Ingestion ──────────────────────────────────────────────────

class DocumentSource(Enum):
    WEB       = "web"       # Fetched from URL
    FILE      = "file"      # Local file (PDF/DOCX/PPTX/HTML)
    DATA      = "data"      # CSV/Excel tabular data
    SUBAGENT  = "subagent"  # Result from a sub-agent

@dataclass
class IngestedDocument:
    """Unified document produced by any ingestion path."""
    source_type: DocumentSource
    source_path: str          # URL or file path
    title: str
    text: str                 # Full extracted text (markdown)
    tables: list[dict]        # Extracted tables as list of {headers, rows}
    images_desc: list[str]    # Image descriptions (from Docling vision)
    metadata: dict            # author, date, page_count, sheet_names, etc.
    raw_chunks: list[str]     # Text split into indexable chunks

# ─── New: Skills ─────────────────────────────────────────────────────────────

@dataclass
class Skill:
    name: str
    description: str
    path: str              # SKILLS/{name}/SKILL.md
    content: str           # Full SKILL.md content
    tags: list[str]        # e.g. ["web", "scraping", "html"]
    version: str           # e.g. "1.0"

# ─── New: Research State ─────────────────────────────────────────────────────

@dataclass
class ResearchState:
    """Mutable shared state across PAC cycles."""
    query: str
    plan: "ResearchPlan"
    docs: list[IngestedDocument]        = field(default_factory=list)
    topics_json: dict                   = field(default_factory=dict)
    scratch_pad: str                    = ""
    rolling_summary: str                = ""
    pac_cycle: int                      = 0
    coverage_scores: dict[str, float]   = field(default_factory=dict)
    spawned_subagent_ids: list[str]     = field(default_factory=list)
    active_skills: list[Skill]          = field(default_factory=list)
    depth: int                          = 0   # Spawning depth (0 = root)

@dataclass
class ActionResult:
    action_type: str       # "search", "fetch", "ingest", "code_exec", "index"
    success: bool
    output: Any            # Result payload
    error: Optional[str]   = None
    tokens_used: int        = 0
    duration_ms: int        = 0

# ─── New: Sub-Agent ──────────────────────────────────────────────────────────

@dataclass
class SubAgentTask:
    task_id: str
    subtopic: str
    parent_depth: int
    config_overrides: dict = field(default_factory=dict)  # smaller max_docs etc.

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

# ─── New: Coverage ───────────────────────────────────────────────────────────

@dataclass
class CoverageReport:
    """Extended GapReport with per-subquestion scores."""
    covered_subtopics: list[str]
    missing_subtopics: list[str]
    contradictions: list[str]
    followup_queries: list[str]
    should_research_more: bool
    coverage_scores: dict[str, float]   # subquestion → 0..1 score
    overall_coverage: float             # weighted average
    recommended_actions: list[str]      # e.g. ["run_code_analysis", "search_academic"]

# ─── New: Experiences ────────────────────────────────────────────────────────

@dataclass
class Experience:
    timestamp: str
    query: str
    outcome: str           # "success" | "partial" | "failure"
    coverage_achieved: float
    skills_used: list[str]
    tools_used: list[str]
    what_worked: str
    what_failed: str
    suggestions: str
    subagents_spawned: int
    total_docs: int
    duration_seconds: float
```

---

## 6. Document Ingestion (Docling)

### 6.1 `ingestion/docling_parser.py`

**Purpose:** Parse PDF, DOCX, PPTX, HTML files into `IngestedDocument` using Docling.

```python
# ingestion/docling_parser.py
from __future__ import annotations
from pathlib import Path
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from omega_researcher.schemas import IngestedDocument, DocumentSource

SUPPORTED_FORMATS = {
    ".pdf":  InputFormat.PDF,
    ".docx": InputFormat.DOCX,
    ".pptx": InputFormat.PPTX,
    ".html": InputFormat.HTML,
    ".htm":  InputFormat.HTML,
}

class DoclingParser:
    def __init__(self, config):
        pipeline_opts = PdfPipelineOptions()
        pipeline_opts.do_ocr = config.docling_ocr
        pipeline_opts.table_structure_options.mode = config.docling_table_mode
        
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_opts)
            }
        )
        self.config = config

    def parse(self, file_path: str | Path) -> IngestedDocument:
        path = Path(file_path)
        ext  = path.suffix.lower()
        
        if ext not in SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format: {ext}")
        
        # Size check
        size_mb = path.stat().st_size / (1024 * 1024)
        if size_mb > self.config.max_file_size_mb:
            raise ValueError(f"File too large: {size_mb:.1f}MB > {self.config.max_file_size_mb}MB")
        
        result = self.converter.convert(str(path))
        doc    = result.document
        
        # Export to markdown (Docling's built-in)
        markdown_text = doc.export_to_markdown()
        
        # Extract tables as structured dicts
        tables = []
        for table in doc.tables:
            try:
                df      = table.export_to_dataframe()
                tables.append({
                    "headers": df.columns.tolist(),
                    "rows":    df.values.tolist(),
                    "caption": getattr(table, "caption", ""),
                })
            except Exception:
                pass
        
        # Image descriptions (Docling includes alt-text / figure captions)
        images_desc = [
            fig.caption_text(doc) 
            for fig in doc.pictures 
            if fig.caption_text(doc)
        ]
        
        # Metadata
        meta = doc.metadata or {}
        metadata = {
            "page_count":    getattr(doc, "num_pages", None),
            "author":        meta.get("author", ""),
            "created":       meta.get("creation_date", ""),
            "title":         meta.get("title", path.stem),
            "file_format":   ext,
            "file_size_mb":  round(size_mb, 2),
        }
        
        # Chunk for indexing (split on double-newline, max 1500 chars each)
        raw_chunks = _chunk_text(markdown_text, max_chars=1500)
        
        return IngestedDocument(
            source_type  = DocumentSource.FILE,
            source_path  = str(path),
            title        = metadata["title"] or path.stem,
            text         = markdown_text,
            tables       = tables,
            images_desc  = images_desc,
            metadata     = metadata,
            raw_chunks   = raw_chunks,
        )

    def parse_batch(self, paths: list[str | Path]) -> list[IngestedDocument]:
        """Parse multiple files, skipping failures with warnings."""
        results = []
        for p in paths:
            try:
                results.append(self.parse(p))
                print(f"[docling] ✓ {p}")
            except Exception as e:
                print(f"[docling] ✗ {p}: {e}")
        return results

def _chunk_text(text: str, max_chars: int = 1500) -> list[str]:
    paragraphs = text.split("\n\n")
    chunks, current = [], ""
    for para in paragraphs:
        if len(current) + len(para) > max_chars and current:
            chunks.append(current.strip())
            current = para
        else:
            current += "\n\n" + para
    if current.strip():
        chunks.append(current.strip())
    return chunks
```

**Key Docling Features Used:**
- `export_to_markdown()` — structured markdown with headings, tables, lists
- `export_to_dataframe()` on tables — gets clean tabular data
- `doc.pictures` — figure captions / alt text
- `PdfPipelineOptions(do_ocr=True)` — handles scanned PDFs

### 6.2 `ingestion/data_reader.py`

**Purpose:** Read CSV/Excel files and expose pandas-style analytics as a callable API (also exposed via MCP data tools).

```python
# ingestion/data_reader.py
from __future__ import annotations
from pathlib import Path
from typing import Any
import pandas as pd
from omega_researcher.schemas import IngestedDocument, DocumentSource

EXCEL_EXTS = {".xlsx", ".xlsm", ".xls", ".ods"}
CSV_EXTS   = {".csv", ".tsv"}

class DataReader:
    """
    Reads structured tabular files into IngestedDocument.
    Also exposes head(), summary(), schema() for MCP tools.
    """
    def __init__(self, config):
        self.config = config
        self._loaded: dict[str, pd.DataFrame] = {}  # cache: path → df

    def load(self, file_path: str | Path) -> pd.DataFrame:
        path = Path(file_path)
        key  = str(path)
        if key not in self._loaded:
            ext = path.suffix.lower()
            if ext in CSV_EXTS:
                sep = "\t" if ext == ".tsv" else ","
                self._loaded[key] = pd.read_csv(path, sep=sep)
            elif ext in EXCEL_EXTS:
                engine = "xlrd" if ext == ".xls" else (
                    "odf" if ext == ".ods" else "openpyxl"
                )
                self._loaded[key] = pd.read_excel(path, engine=engine)
            else:
                raise ValueError(f"Unsupported data format: {ext}")
        return self._loaded[key]

    def head(self, file_path: str, n: int = 5) -> str:
        """Return first N rows as markdown table."""
        df = self.load(file_path)
        return df.head(n).to_markdown(index=False)

    def summary(self, file_path: str) -> str:
        """Return df.describe() + dtypes as markdown."""
        df = self.load(file_path)
        desc  = df.describe(include="all").to_markdown()
        dtype = df.dtypes.to_frame("dtype").to_markdown()
        return f"### Shape\n{df.shape}\n\n### dtypes\n{dtype}\n\n### describe()\n{desc}"

    def schema(self, file_path: str) -> str:
        """Return column names, dtypes, null counts."""
        df = self.load(file_path)
        info = []
        for col in df.columns:
            null_count = df[col].isna().sum()
            info.append(f"- `{col}` ({df[col].dtype}) — {null_count} nulls")
        return "### Schema\n" + "\n".join(info)

    def to_ingested_document(self, file_path: str | Path) -> IngestedDocument:
        """Convert to unified IngestedDocument for indexer."""
        path = Path(file_path)
        df   = self.load(str(path))
        
        # For multi-sheet Excel, load all sheets
        sheets_text = ""
        if path.suffix.lower() in EXCEL_EXTS:
            xl = pd.ExcelFile(path)
            for sheet in xl.sheet_names:
                sdf = pd.read_excel(path, sheet_name=sheet)
                sheets_text += f"\n\n## Sheet: {sheet}\n{sdf.head(50).to_markdown()}"
        
        text = self.summary(str(path)) + "\n\n## Preview\n" + self.head(str(path), 20) + sheets_text
        
        return IngestedDocument(
            source_type = DocumentSource.DATA,
            source_path = str(path),
            title       = path.stem,
            text        = text,
            tables      = [{"headers": df.columns.tolist(), "rows": df.head(100).values.tolist()}],
            images_desc = [],
            metadata    = {
                "rows": len(df), "columns": len(df.columns),
                "dtypes": df.dtypes.astype(str).to_dict(),
                "file_format": path.suffix.lower(),
            },
            raw_chunks  = [text],
        )
```

**How files are passed to the system:**

```python
# In deep_search() / orchestrator call
result = await deep_search(
    query  = "Analyze sales trends and correlate with market data",
    config = Config(max_docs=50),
    
    # File inputs: paths passed directly
    file_paths = [
        "uploads/annual_report.pdf",
        "uploads/company_deck.pptx",
        "uploads/financial_data.xlsx",
        "uploads/customer_data.csv",
    ],
)
```

The orchestrator's `_ingest_all_files(file_paths)` method:
1. Detects each file extension
2. Routes to `DoclingParser.parse()` or `DataReader.to_ingested_document()`
3. Adds all results to `state.docs` before the PAC loop starts
4. Indexes them immediately (INDEX-AS-YOU-GO even for uploaded files)

---

## 7. Memory System

### 7.1 `memory/index_manager.py` — Live Index Access

Wraps `synthesizer/indexer.py` but adds a **live-read API** so that during indexing, the actor can query what was already indexed.

```python
# memory/index_manager.py
class IndexManager:
    def __init__(self, config: Config):
        self.indexes_dir = Path(config.indexes_dir)
        self.config = config
        self._topics_json: dict = {}
    
    def index_document(self, doc: IngestedDocument, query: str, llm, scratch_pad: str) -> dict:
        """
        INDEX-AS-YOU-GO: Index a single document immediately after processing.
        Updates self._topics_json in memory AND writes to INDEXES/.
        Returns updated topics_json so actor can see what was just learned.
        """
        # Same logic as existing indexer.py, but called per-document
        # instead of batch at the end.
        ...
    
    def get_topics(self) -> dict:
        """Current in-memory topics hierarchy."""
        return self._topics_json
    
    def read_index_file(self, path: list[str]) -> str:
        """Read a specific INDEXES/<path>/information.md or overview.md"""
        target = self.indexes_dir.joinpath(*path)
        for fname in ["overview.md", "information.md"]:
            f = target / fname
            if f.exists():
                return f.read_text(encoding="utf-8")
        return ""
    
    def list_topics(self) -> list[str]:
        """Returns all leaf topic paths as strings like 'AI/NLP/Transformers'."""
        results = []
        for p in self.indexes_dir.rglob("information.md"):
            rel = p.parent.relative_to(self.indexes_dir)
            results.append(str(rel))
        return results
```

### 7.2 `memory/rolling_summary.py`

**Purpose:** As the actor processes more documents, the context window fills up. Rolling summary compresses it on demand.

```python
# memory/rolling_summary.py
class RollingSummary:
    """
    Maintains a compressed rolling summary of research progress.
    Auto-compresses when token estimate exceeds threshold.
    """
    def __init__(self, config: Config, llm_client):
        self.path      = Path(config.rolling_summary_path)
        self.max_tokens = config.rolling_summary_max_tokens
        self.llm       = llm_client
        self._text     = self._load()
    
    def _load(self) -> str:
        return self.path.read_text(encoding="utf-8") if self.path.exists() else ""
    
    def update(self, new_info: str, context: str = "") -> None:
        """
        Append new information. If too long, compress via LLM.
        new_info: what was just learned / done
        context: current query for relevance filtering
        """
        self._text += f"\n\n---\n{new_info}"
        
        # Estimate tokens (rough: 4 chars ≈ 1 token)
        if len(self._text) // 4 > self.max_tokens:
            self._compress(context)
        
        self.path.write_text(self._text, encoding="utf-8")
    
    def _compress(self, context: str) -> None:
        prompt = f"""
The following is a rolling research summary that has grown too long.
Research query context: {context}

Compress this into a dense, information-rich summary (keep all key facts, 
discoveries, contradictions, and open questions). Target ~800 tokens.

CURRENT SUMMARY:
{self._text}
"""
        compressed = self.llm.generate(
            prompt, 
            system="You are a lossless research summarizer. Keep all key findings.",
            max_tokens=1200
        )
        self._text = f"[COMPRESSED SUMMARY]\n{compressed}"
        print("[rolling_summary] Compressed context.")
    
    def get(self) -> str:
        return self._text
    
    def reset(self) -> None:
        self._text = ""
        if self.path.exists():
            self.path.unlink()
```

### 7.3 `memory/scratch_pad.py`

**Purpose:** Shared mutable scratch pad — a live "working memory" writable by any agent (thread-safe for parallel subagents).

```python
# memory/scratch_pad.py
import threading
from pathlib import Path

class ScratchPad:
    """
    Thread-safe scratch pad for shared ephemeral notes.
    All agents (including subagents) write here.
    Think of it as the researcher's physical notepad.
    
    Structure:
    ## Global Notes
    ...
    ## SubAgent: {task_id}
    ...
    ## Contradictions
    ...
    ## Open Questions
    ...
    """
    _lock = threading.Lock()

    def __init__(self, path: str):
        self.path = Path(path)
        self._sections: dict[str, str] = {"Global Notes": "", "Contradictions": "", "Open Questions": ""}
        if self.path.exists():
            self._load()
    
    def write(self, section: str, content: str) -> None:
        with self._lock:
            self._sections[section] = content
            self._flush()
    
    def append(self, section: str, content: str) -> None:
        with self._lock:
            self._sections.setdefault(section, "")
            self._sections[section] += f"\n{content}"
            self._flush()
    
    def read(self, section: str | None = None) -> str:
        if section:
            return self._sections.get(section, "")
        return "\n\n".join(
            f"## {k}\n{v}" for k, v in self._sections.items() if v.strip()
        )
    
    def _flush(self) -> None:
        text = "# Scratch Pad\n\n" + self.read()
        self.path.write_text(text, encoding="utf-8")
    
    def _load(self) -> None:
        text = self.path.read_text(encoding="utf-8")
        # Parse ## Section headers
        import re
        matches = re.split(r'^## (.+)$', text, flags=re.MULTILINE)
        # matches: ['prefix', 'SectionName', 'content', 'SectionName2', 'content2', ...]
        for i in range(1, len(matches) - 1, 2):
            self._sections[matches[i].strip()] = matches[i+1].strip()
```

### 7.4 `memory/experiences.py`

```python
# memory/experiences.py
import json
from pathlib import Path
from datetime import datetime
from omega_researcher.schemas import Experience

class ExperienceLogger:
    """
    Append-only log of research outcomes.
    Written by MetaAgent in a separate LLM context.
    Format: JSONL (one Experience per line) + human-readable experiences.md
    """
    def __init__(self, config):
        self.path      = Path(config.experiences_path)
        self.jsonl_path = self.path.with_suffix(".jsonl")
    
    def log(self, exp: Experience) -> None:
        """Append experience to both JSONL and markdown."""
        # JSONL for machine reading
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(exp.__dict__) + "\n")
        
        # Markdown for human reading + LLM reading
        md = f"""
---
## Experience: {exp.timestamp}
**Query:** {exp.query}
**Outcome:** {exp.outcome} (coverage: {exp.coverage_achieved:.0%})
**Duration:** {exp.duration_seconds:.1f}s | **Docs:** {exp.total_docs} | **Subagents:** {exp.subagents_spawned}

**Skills used:** {", ".join(exp.skills_used) or "none"}
**Tools used:** {", ".join(exp.tools_used)}

### What worked
{exp.what_worked}

### What failed
{exp.what_failed}

### Suggestions for next time
{exp.suggestions}
"""
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(md)
    
    def read_all(self) -> list[Experience]:
        if not self.jsonl_path.exists():
            return []
        results = []
        with open(self.jsonl_path, "r") as f:
            for line in f:
                try:
                    results.append(Experience(**json.loads(line)))
                except Exception:
                    pass
        return results
    
    def read_failures(self) -> list[Experience]:
        return [e for e in self.read_all() if e.outcome in ("failure", "partial")]
    
    def read_for_query_type(self, query_keywords: list[str]) -> list[Experience]:
        all_exp = self.read_all()
        return [e for e in all_exp 
                if any(kw.lower() in e.query.lower() for kw in query_keywords)]
```

### 7.5 `search/index_search.py` — `search_from_indexes()`

```python
# search/index_search.py
from pathlib import Path
from omega_researcher.config import Config

class IndexSearch:
    """
    Searches the INDEXES/ directory tree for content matching a query.
    
    Strategy:
    1. Scan all information.md + overview.md files
    2. Simple keyword + TF-IDF ranking (no vector DB needed)
    3. Return top-K matching chunks with source paths
    
    For production: replace with a local vector store (chromadb, faiss)
    """
    def __init__(self, config: Config):
        self.indexes_dir = Path(config.indexes_dir)
        self.top_k = config.index_search_top_k
    
    def search(self, query: str) -> list[dict]:
        """
        Returns list of {path, content_snippet, relevance_score}
        sorted by relevance.
        """
        query_words = set(query.lower().split())
        results = []
        
        for md_file in self.indexes_dir.rglob("*.md"):
            text = md_file.read_text(encoding="utf-8", errors="ignore")
            # Score: count query word hits
            text_lower = text.lower()
            score = sum(text_lower.count(w) for w in query_words)
            if score > 0:
                # Extract best snippet (200 chars around highest density)
                snippet = _best_snippet(text, query_words, 300)
                results.append({
                    "path":     str(md_file.relative_to(self.indexes_dir)),
                    "snippet":  snippet,
                    "score":    score,
                    "full_path": str(md_file),
                })
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:self.top_k]
    
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
    best_pos, best_score = 0, 0
    text_lower = text.lower()
    for i in range(0, len(text) - length, 50):
        window = text_lower[i:i + length]
        score  = sum(window.count(w) for w in query_words)
        if score > best_score:
            best_score, best_pos = score, i
    return text[best_pos:best_pos + length].strip()
```

---

## 8. Dynamic Skills System

### 8.1 Skill Format (`SKILLS/*/SKILL.md`)

Each skill follows this template:

```markdown
---
name: data_analysis
description: >
  Use when the research involves tabular data, statistical analysis,
  pandas/numpy operations, correlation studies, or quantitative findings.
tags: [data, analysis, statistics, pandas, csv, excel]
version: 1.0
---

# Data Analysis Skill

## When to activate this skill
- Query mentions numbers, statistics, trends, correlations, distributions
- User provides CSV or Excel files
- Research requires quantitative evidence

## Recommended tool sequence
1. `read_data(file_path)` → get schema and summary
2. `execute_code(pandas_script)` → run analytics
3. `search_from_indexes()` → cross-reference with indexed knowledge
4. Update scratch pad with key statistics found

## Prompting guidance
When calling the LLM for data analysis tasks:
- Ask for Python pandas code to explore the data
- Request interpretation of statistical outputs
- Ask to flag outliers and anomalies
- Use correlation matrices before drawing causal conclusions

## Common pitfalls to avoid
- Do not confuse correlation with causation
- Always check for missing data before computing stats
- Normalize distributions before comparing across datasets
```

### 8.2 `skills/skill_loader.py`

```python
# skills/skill_loader.py
from pathlib import Path
from omega_researcher.schemas import Skill
from omega_researcher.config import Config

class SkillLoader:
    def __init__(self, config: Config):
        self.skills_dir = Path(config.skills_dir)
        self._cache: dict[str, Skill] = {}
    
    def load_all(self) -> list[Skill]:
        """Load all SKILLS/*/SKILL.md files."""
        skills = []
        for skill_file in self.skills_dir.rglob("SKILL.md"):
            try:
                skill = self._parse_skill_file(skill_file)
                self._cache[skill.name] = skill
                skills.append(skill)
            except Exception as e:
                print(f"[skill_loader] Failed to load {skill_file}: {e}")
        return skills
    
    def load_for_task(self, task_description: str, llm) -> list[Skill]:
        """
        Use LLM to select which skills are relevant for this task.
        Returns a subset of loaded skills.
        """
        all_skills = self.load_all()
        if not all_skills:
            return []
        
        skills_summary = "\n".join(
            f"- {s.name}: {s.description[:200]}" for s in all_skills
        )
        prompt = f"""
Task: {task_description}

Available skills:
{skills_summary}

Which skills are relevant for this task? Return a JSON list of skill names.
Example: ["data_analysis", "web_scraping"]
"""
        try:
            selected = llm.json(prompt, system="Return JSON list of skill names only.")
            return [self._cache[n] for n in selected if n in self._cache]
        except Exception:
            return []
    
    def get(self, name: str) -> Skill | None:
        return self._cache.get(name)
    
    def _parse_skill_file(self, path: Path) -> Skill:
        content = path.read_text(encoding="utf-8")
        # Parse YAML frontmatter
        import yaml
        parts = content.split("---", 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1])
        else:
            meta = {}
        return Skill(
            name        = meta.get("name", path.parent.name),
            description = str(meta.get("description", "")),
            path        = str(path),
            content     = content,
            tags        = meta.get("tags", []),
            version     = str(meta.get("version", "1.0")),
        )
```

### 8.3 `skills/skill_creator.py`

```python
# skills/skill_creator.py
from pathlib import Path
from datetime import datetime
from omega_researcher.config import Config

class SkillCreator:
    """
    create_skill(): Called by the Actor when it encounters a new task type
    it has no skill for, or by MetaAgent after analyzing experiences.
    """
    def __init__(self, config: Config, llm):
        self.skills_dir = Path(config.skills_dir)
        self.llm = llm
    
    def create_skill(
        self,
        task_description: str,
        what_worked: str,
        name: str | None = None,
    ) -> str:
        """
        Generate a new SKILL.md from observations about what worked.
        Returns the path of the created skill file.
        """
        prompt = f"""
You are creating a reusable skill file for a research agent system.

A skill file documents HOW to handle a particular type of research task.
It includes: when to use the skill, what tools to call, prompting guidance, pitfalls.

Task type encountered:
{task_description}

What worked during this task:
{what_worked}

Generate a complete SKILL.md in this exact format:
---
name: <snake_case_name>
description: <2-3 sentence description of when to activate this skill>
tags: [<comma, separated, tags>]
version: 1.0
---

# <Skill Title>

## When to activate this skill
<bullet list of trigger conditions>

## Recommended tool sequence
<numbered steps>

## Prompting guidance
<how to prompt the LLM for this task type>

## Common pitfalls to avoid
<bullet list>
"""
        skill_content = self.llm.generate(
            prompt, 
            system="Generate a concise, actionable SKILL.md file. No extra commentary.",
            max_tokens=2000
        )
        
        # Extract name from content
        import re, yaml
        parts = skill_content.split("---", 2)
        if len(parts) >= 3:
            meta = yaml.safe_load(parts[1])
            skill_name = meta.get("name", name or "custom_skill")
        else:
            skill_name = name or "custom_skill"
        
        skill_dir  = self.skills_dir / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(skill_content, encoding="utf-8")
        
        print(f"[skill_creator] Created skill: {skill_file}")
        return str(skill_file)
    
    def update_skill(self, skill_name: str, new_observations: str) -> str:
        """Update an existing skill with new learnings from experiences.md."""
        skill_path = self.skills_dir / skill_name / "SKILL.md"
        if not skill_path.exists():
            return self.create_skill(new_observations, new_observations, skill_name)
        
        current = skill_path.read_text(encoding="utf-8")
        prompt = f"""
Update the following skill file with new learnings. Keep the format identical.
Only update the content based on new observations — don't remove existing good advice.
Increment the version number.

CURRENT SKILL:
{current}

NEW OBSERVATIONS:
{new_observations}
"""
        updated = self.llm.generate(prompt, max_tokens=2000)
        skill_path.write_text(updated, encoding="utf-8")
        return str(skill_path)
```

---

## 9. MCP Server & Tools

### 9.1 `mcp/mcp_server.py`

Uses **FastMCP** (from the `mcp` Python package) to expose all tools as an MCP server.

```python
# mcp/mcp_server.py
from mcp.server.fastmcp import FastMCP
from omega_researcher.config import Config
from omega_researcher.mcp.tools.code_executor   import CodeExecutor
from omega_researcher.mcp.tools.data_tools      import DataTools
from omega_researcher.mcp.tools.search_tools    import SearchTools
from omega_researcher.mcp.tools.file_tools      import FileTools
from omega_researcher.mcp.tools.skill_tools     import SkillTools

def build_mcp_server(config: Config, llm, index_manager, skill_loader, 
                     scratch_pad, rolling_summary) -> FastMCP:
    
    mcp = FastMCP("OmegaResearcher")
    
    executor = CodeExecutor(config)
    data     = DataTools(config)
    search   = SearchTools(config, index_manager)
    files    = FileTools(config, llm)
    skills   = SkillTools(config, llm, skill_loader)
    
    # ─── Code Execution ───────────────────────────────────────────────────
    @mcp.tool()
    def execute_python(code: str, timeout_seconds: int = 30) -> str:
        """
        Execute Python code in isolated Docker sandbox with pandas, numpy, 
        sklearn, matplotlib, scipy, statsmodels pre-installed.
        Returns stdout + any printed DataFrames.
        """
        return executor.run(code, timeout_seconds)
    
    # ─── Data Tools ───────────────────────────────────────────────────────
    @mcp.tool()
    def data_head(file_path: str, n: int = 10) -> str:
        """Return first N rows of a CSV/Excel file as markdown table."""
        return data.head(file_path, n)
    
    @mcp.tool()
    def data_summary(file_path: str) -> str:
        """Return statistical summary (describe, dtypes, nulls) of a data file."""
        return data.summary(file_path)
    
    @mcp.tool()
    def data_schema(file_path: str) -> str:
        """Return column names, types, and null counts of a data file."""
        return data.schema(file_path)
    
    @mcp.tool()
    def data_query(file_path: str, pandas_query: str) -> str:
        """
        Run a pandas .query() expression on a loaded dataframe.
        Example: data_query("data.csv", "age > 30 and salary > 50000")
        """
        return data.query(file_path, pandas_query)
    
    # ─── Search Tools ─────────────────────────────────────────────────────
    @mcp.tool()
    def searxng_search(query: str, categories: str = "general", max_results: int = 10) -> str:
        """
        On-demand SearxNG search (supplemental to the main deep_search loop).
        Use for targeted lookups during research.
        """
        return search.searxng_search(query, categories, max_results)
    
    @mcp.tool()
    def search_from_indexes(query: str) -> str:
        """
        Search the INDEXES/ knowledge tree for previously indexed content.
        Use this to recall what was already learned earlier in this research session.
        Critical for consistency and avoiding re-research.
        """
        return search.search_indexes(query)
    
    @mcp.tool()
    def list_indexed_topics() -> str:
        """List all topics currently in the INDEXES/ knowledge tree."""
        return search.list_topics()
    
    # ─── File Ingestion ───────────────────────────────────────────────────
    @mcp.tool()
    def ingest_document(file_path: str) -> str:
        """
        Parse a PDF, DOCX, PPTX, or HTML file using Docling.
        Returns structured markdown text. File is also indexed automatically.
        """
        return files.ingest(file_path)
    
    @mcp.tool()
    def ingest_data_file(file_path: str) -> str:
        """
        Load a CSV or Excel file and return its schema + preview.
        File is registered for use with data_head/data_summary/execute_python.
        """
        return files.ingest_data(file_path)
    
    # ─── Skill Tools ──────────────────────────────────────────────────────
    @mcp.tool()
    def list_skills() -> str:
        """List all available skills in SKILLS/."""
        return skills.list_all()
    
    @mcp.tool()
    def load_skill(skill_name: str) -> str:
        """Load and return the full content of a specific SKILL.md."""
        return skills.load(skill_name)
    
    @mcp.tool()
    def create_skill(task_description: str, what_worked: str, name: str = "") -> str:
        """
        Create a new skill from observations. Use when facing a novel task type.
        The skill will be saved to SKILLS/{name}/SKILL.md for future reuse.
        """
        return skills.create(task_description, what_worked, name)
    
    # ─── Memory Tools ─────────────────────────────────────────────────────
    @mcp.tool()
    def read_scratch_pad(section: str = "") -> str:
        """Read the current scratch pad. Optionally specify a section name."""
        return scratch_pad.read(section or None)
    
    @mcp.tool()
    def write_scratch_pad(section: str, content: str) -> str:
        """Write/update a scratch pad section."""
        scratch_pad.write(section, content)
        return f"Written to scratch pad section '{section}'"
    
    @mcp.tool()
    def append_scratch_pad(section: str, note: str) -> str:
        """Append a note to a scratch pad section."""
        scratch_pad.append(section, note)
        return f"Appended to scratch pad section '{section}'"
    
    @mcp.tool()
    def get_rolling_summary() -> str:
        """Get the current rolling research summary (compressed context)."""
        return rolling_summary.get()
    
    return mcp
```

### 9.2 `mcp/tools/code_executor.py` — Docker Sandbox

```python
# mcp/tools/code_executor.py
import docker
import tempfile
import os
from omega_researcher.config import Config

ANALYTICS_LIBS_AVAILABLE = """
# Pre-installed in the sandbox:
# pandas, numpy, sklearn, scipy, statsmodels, matplotlib, seaborn,
# plotly, openpyxl, xlrd, tabulate, pyarrow
# Files from the research session are mounted at /data/
"""

class CodeExecutor:
    def __init__(self, config: Config):
        self.config  = config
        self.image   = config.docker_executor_image
        self.timeout = config.docker_executor_timeout
        try:
            self.client = docker.from_env()
        except Exception:
            self.client = None
            print("[code_executor] Docker not available — code execution disabled")
    
    def run(self, code: str, timeout: int | None = None) -> str:
        """
        Execute Python code in isolated container.
        Returns stdout (truncated to 5000 chars) or error message.
        """
        if not self.client:
            return "[ERROR] Docker not available. Cannot execute code."
        
        timeout = timeout or self.timeout
        
        # Prepend available libs info
        full_code = ANALYTICS_LIBS_AVAILABLE + "\n" + code
        
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", delete=False, encoding="utf-8"
            ) as f:
                f.write(full_code)
                script_path = f.name
            
            container = self.client.containers.run(
                image        = self.image,
                command      = f"python /script/run.py",
                volumes      = {
                    script_path:   {"bind": "/script/run.py", "mode": "ro"},
                    os.getcwd():   {"bind": "/data",          "mode": "ro"},
                },
                network      = self.config.docker_network,
                mem_limit    = "512m",
                cpu_quota    = 50000,     # 50% of one CPU
                remove       = True,
                detach       = False,
                timeout      = timeout,
                stdout       = True,
                stderr       = True,
            )
            
            output = container.decode("utf-8") if isinstance(container, bytes) else str(container)
            return output[:5000]  # Truncate large outputs
        
        except Exception as e:
            return f"[code_executor ERROR] {type(e).__name__}: {e}"
        finally:
            try: os.unlink(script_path)
            except: pass
```

**`docker/Dockerfile.executor`:**

```dockerfile
FROM python:3.11-slim

# Analytics stack
RUN pip install --no-cache-dir \
    pandas numpy scipy scikit-learn statsmodels \
    matplotlib seaborn plotly \
    openpyxl xlrd xlwt tabulate pyarrow \
    requests httpx

# Security: non-root user
RUN useradd -m executor
USER executor
WORKDIR /workspace

CMD ["python"]
```

**`docker/docker-compose.yml`:**

```yaml
version: "3.9"

networks:
  omega_net:
    driver: bridge

services:
  searxng:
    image: searxng/searxng:latest
    ports: ["8080:8080"]
    networks: [omega_net]
    volumes:
      - ./searxng-settings.yml:/etc/searxng/settings.yml
    environment:
      - SEARXNG_SECRET_KEY=change_me_in_production

  executor:
    build:
      context: .
      dockerfile: Dockerfile.executor
    image: omega-executor:latest
    networks: [omega_net]
    read_only: true
    tmpfs: [/tmp]
    security_opt: [no-new-privileges:true]
```

---

## 10. Multi-Agent Sub-Spawner

### 10.1 `agents/subagent_spawner.py`

```python
# agents/subagent_spawner.py
from __future__ import annotations
import asyncio
import uuid
from omega_researcher.config import Config
from omega_researcher.schemas import SubAgentTask, SubAgentResult, ResearchState

class SubagentSpawner:
    """
    Spawns parallel sub-agents for independent subtopics.
    Each sub-agent runs its own PAC loop recursively.
    Respects SPAWNING_DEPTH_LIMIT = 3.
    
    Depth semantics:
    - depth=0: root research agent
    - depth=1: first-level subagents (up to max_subagents)
    - depth=2: second-level subagents
    - depth=3: leaf subagents (cannot spawn further)
    """
    def __init__(self, config: Config, llm, memory_system, skill_loader):
        self.config       = config
        self.llm          = llm
        self.memory       = memory_system
        self.skill_loader = skill_loader
    
    async def spawn_for_subquestions(
        self, 
        subquestions: list[str],
        parent_state: ResearchState,
    ) -> list[SubAgentResult]:
        """
        Spawn one sub-agent per subquestion (up to max_subagents).
        Runs them in parallel via asyncio.gather.
        """
        current_depth = parent_state.depth
        
        if current_depth >= self.config.SPAWNING_DEPTH_LIMIT:
            print(f"[spawner] Depth limit {self.config.SPAWNING_DEPTH_LIMIT} reached — not spawning")
            return []
        
        # Limit parallel subagents
        tasks = [
            SubAgentTask(
                task_id       = str(uuid.uuid4())[:8],
                subtopic      = sq,
                parent_depth  = current_depth,
                config_overrides = {
                    "max_docs":    self.config.subagent_max_docs,
                    "max_pac_cycles": 5,
                },
            )
            for sq in subquestions[:self.config.max_subagents]
        ]
        
        print(f"[spawner] Spawning {len(tasks)} sub-agents at depth {current_depth + 1}")
        
        results = await asyncio.gather(
            *[self._run_subagent(task, parent_state) for task in tasks],
            return_exceptions=True
        )
        
        # Filter out exceptions
        valid = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                print(f"[spawner] Sub-agent {tasks[i].task_id} failed: {r}")
                valid.append(SubAgentResult(
                    task_id=tasks[i].task_id,
                    subtopic=tasks[i].subtopic,
                    docs=[], topics_json={}, scratch_pad="",
                    report_section="",
                    success=False, error=str(r)
                ))
            else:
                valid.append(r)
        
        return valid
    
    async def _run_subagent(
        self, task: SubAgentTask, parent_state: ResearchState
    ) -> SubAgentResult:
        """
        Run a single sub-agent: creates an isolated Orchestrator instance
        with reduced budgets, inherits parent's INDEXES/ knowledge.
        """
        from omega_researcher.orchestrator import Orchestrator
        
        # Build child config with overrides
        child_cfg_dict = {
            k: getattr(self.config, k) 
            for k in self.config.__dataclass_fields__
        }
        child_cfg_dict.update(task.config_overrides)
        child_cfg = type(self.config)(**child_cfg_dict)
        
        # Inherit parent's rolling summary so subagent knows what's been done
        inherited_summary = parent_state.rolling_summary
        
        try:
            async with asyncio.timeout(self.config.subagent_timeout):
                orchestrator = Orchestrator(
                    config  = child_cfg,
                    depth   = task.parent_depth + 1,
                    # Subagent SHARES the same INDEXES/ dir → INDEX-AS-YOU-GO
                    # across the entire agent tree
                    shared_indexes_dir = self.config.indexes_dir,
                    initial_rolling_summary = inherited_summary,
                )
                
                state = await orchestrator.run(
                    query      = task.subtopic,
                    file_paths = [],
                )
                
                return SubAgentResult(
                    task_id        = task.task_id,
                    subtopic       = task.subtopic,
                    docs           = state.docs,
                    topics_json    = state.topics_json,
                    scratch_pad    = state.scratch_pad,
                    report_section = state.rolling_summary,
                    success        = True,
                )
        except asyncio.TimeoutError:
            return SubAgentResult(
                task_id=task.task_id, subtopic=task.subtopic,
                docs=[], topics_json={}, scratch_pad="",
                report_section="[Subagent timed out]",
                success=False, error="Timeout"
            )
    
    def merge_results(
        self, parent_state: ResearchState, results: list[SubAgentResult]
    ) -> ResearchState:
        """
        Merge sub-agent results back into parent state.
        - docs: append
        - topics_json: deep merge
        - scratch_pad: create per-subagent section
        """
        for result in results:
            if result.success:
                parent_state.docs.extend(result.docs)
                _deep_merge(parent_state.topics_json, result.topics_json)
                parent_state.scratch_pad += f"\n\n## SubAgent: {result.subtopic}\n{result.scratch_pad}"
                parent_state.spawned_subagent_ids.append(result.task_id)
        return parent_state

def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override dict into base dict."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base
```

---

## 11. Planner–Actor–Critic (PAC) Framework

### 11.1 `orchestrator.py`

The top-level coordinator. Manages the PAC loop.

```python
# orchestrator.py
from __future__ import annotations
import asyncio
import time
from omega_researcher.config import Config
from omega_researcher.schemas import ResearchState, IngestedDocument
from omega_researcher.agents.planner_agent import PlannerAgent
from omega_researcher.agents.actor_agent   import ActorAgent
from omega_researcher.agents.critic_agent  import CriticAgent
from omega_researcher.agents.meta_agent    import MetaAgent
from omega_researcher.memory.scratch_pad   import ScratchPad
from omega_researcher.memory.rolling_summary import RollingSummary
from omega_researcher.memory.index_manager  import IndexManager
from omega_researcher.memory.experiences    import ExperienceLogger
from omega_researcher.skills.skill_loader   import SkillLoader
from omega_researcher.ingestion.docling_parser import DoclingParser
from omega_researcher.ingestion.data_reader    import DataReader
from omega_researcher.llm_client               import LLMClient
from omega_researcher.mcp.mcp_server           import build_mcp_server

class Orchestrator:
    def __init__(
        self,
        config: Config | None = None,
        depth: int = 0,
        shared_indexes_dir: str | None = None,
        initial_rolling_summary: str = "",
    ):
        self.config  = config or Config()
        self.depth   = depth
        
        if shared_indexes_dir:
            self.config.indexes_dir = shared_indexes_dir
        
        # ── Core infrastructure
        self.llm            = LLMClient(self.config)
        self.scratch_pad    = ScratchPad(self.config.scratch_pad_path)
        self.rolling_summary = RollingSummary(self.config, self.llm)
        self.index_manager  = IndexManager(self.config)
        self.skill_loader   = SkillLoader(self.config)
        self.exp_logger     = ExperienceLogger(self.config)
        
        if initial_rolling_summary:
            self.rolling_summary._text = initial_rolling_summary
        
        # ── MCP server (built once, shared across agents)
        self.mcp = build_mcp_server(
            self.config, self.llm, self.index_manager,
            self.skill_loader, self.scratch_pad, self.rolling_summary
        )
        
        # ── PAC Agents
        self.planner = PlannerAgent(self.config, self.llm, self.skill_loader)
        self.actor   = ActorAgent(self.config, self.llm, self.mcp, self.index_manager,
                                  self.scratch_pad, self.rolling_summary, self.skill_loader)
        self.critic  = CriticAgent(self.config, self.llm)
        self.meta    = MetaAgent(self.config)  # SEPARATE — no shared context
    
    async def run(
        self,
        query: str,
        file_paths: list[str] | None = None,
    ) -> ResearchState:
        
        start_time = time.time()
        print(f"\n{'='*60}")
        print(f"[orchestrator] Starting research: {query[:80]}")
        print(f"[orchestrator] Depth: {self.depth} | Files: {len(file_paths or [])}")
        print(f"{'='*60}\n")
        
        # 1. INGEST uploaded files immediately
        docs = await self._ingest_files(file_paths or [])
        
        # 2. PLANNER: Build research plan (skill-aware)
        plan = self.planner.make_plan(query, pre_ingested_docs=docs)
        
        state = ResearchState(
            query   = query,
            plan    = plan,
            docs    = docs,
            depth   = self.depth,
        )
        
        # 3. Index pre-ingested files before PAC loop
        for doc in docs:
            self.index_manager.index_document(doc, query, self.llm, state.scratch_pad)
        
        # 4. PAC LOOP
        for cycle in range(self.config.max_pac_cycles):
            state.pac_cycle = cycle
            print(f"\n[PAC cycle {cycle+1}/{self.config.max_pac_cycles}]")
            
            # ACTOR: Execute actions
            state = await self.actor.run_cycle(state)
            
            # CRITIC: Evaluate coverage
            coverage = self.critic.evaluate(query, state)
            state.coverage_scores = coverage.coverage_scores
            
            print(f"[critic] Overall coverage: {coverage.overall_coverage:.0%}")
            
            # Update rolling summary with cycle outcome
            self.rolling_summary.update(
                f"PAC cycle {cycle+1}: coverage={coverage.overall_coverage:.0%}, "
                f"docs={len(state.docs)}, gaps={len(coverage.missing_subtopics)}",
                context=query
            )
            
            # Stop conditions
            if not coverage.should_research_more:
                print(f"[orchestrator] Coverage threshold reached → synthesizing")
                break
            
            if len(state.docs) >= self.config.max_docs:
                print(f"[orchestrator] max_docs={self.config.max_docs} reached → synthesizing")
                break
            
            # Feed gaps back to actor for next cycle
            state.plan.queries.extend(coverage.followup_queries)
        
        # 5. SYNTHESIZE
        from omega_researcher.synthesizer.synthesizer import Synthesizer
        synthesizer = Synthesizer(self.llm, self.config)
        report = synthesizer.synthesize(query, state)
        
        # 6. META-AGENT (separate LLM call, doesn't pollute state)
        asyncio.create_task(
            self._run_meta_eval(query, plan, report, state, start_time)
        )
        
        state.rolling_summary = report
        return state
    
    async def _ingest_files(self, file_paths: list[str]) -> list[IngestedDocument]:
        """Ingest all uploaded files before research starts."""
        docling = DoclingParser(self.config)
        data_reader = DataReader(self.config)
        
        docs = []
        DOCLING_EXTS = {".pdf", ".docx", ".pptx", ".html", ".htm"}
        DATA_EXTS    = {".csv", ".tsv", ".xlsx", ".xlsm", ".xls", ".ods"}
        
        for fp in file_paths:
            from pathlib import Path
            ext = Path(fp).suffix.lower()
            try:
                if ext in DOCLING_EXTS:
                    docs.append(docling.parse(fp))
                elif ext in DATA_EXTS:
                    docs.append(data_reader.to_ingested_document(fp))
                else:
                    print(f"[orchestrator] Unknown file type: {fp}")
            except Exception as e:
                print(f"[orchestrator] Failed to ingest {fp}: {e}")
        
        return docs
    
    async def _run_meta_eval(self, query, plan, report, state, start_time):
        """Run MetaAgent post-evaluation in fire-and-forget fashion."""
        try:
            await self.meta.post_eval(
                query=query, plan=plan, report=report, state=state,
                duration_seconds=time.time() - start_time
            )
        except Exception as e:
            print(f"[meta_agent] Post-eval failed: {e}")


# ── Public API ────────────────────────────────────────────────────────────────

async def deep_research(
    query: str,
    config: Config | dict | None = None,
    file_paths: list[str] | None = None,
) -> str:
    """
    Main entry point. Backward-compatible with original deep_search().
    
    Args:
        query:      Research topic or question
        config:     Config object or dict of overrides
        file_paths: Local files to ingest (PDF/DOCX/PPTX/HTML/CSV/Excel)
    
    Returns:
        Final research report as markdown string
    """
    if isinstance(config, dict):
        cfg = Config(**config)
    elif config is None:
        cfg = Config()
    else:
        cfg = config
    
    orch   = Orchestrator(config=cfg)
    state  = await orch.run(query=query, file_paths=file_paths or [])
    return state.rolling_summary   # final report
```

### 11.2 `agents/planner_agent.py`

```python
# agents/planner_agent.py
class PlannerAgent:
    """
    Enhanced planner: loads relevant skills, decides whether to spawn subagents,
    generates enriched ResearchPlan.
    """
    SYSTEM_PROMPT = """You are an expert research strategist.
Given a research query, available skills, and any pre-ingested document summaries:
1. Generate a structured research plan
2. Decide if subquestions should be researched by parallel sub-agents
3. Identify which MCP tools will be needed
Return strictly JSON (no extra text):
{
  "topic": "...",
  "subquestions": ["..."],
  "queries": ["..."],
  "source_preferences": ["academic", "official", ...],
  "spawn_subagents": true/false,
  "subagent_topics": ["...", "..."],   // only if spawn_subagents=true
  "required_tools": ["execute_python", "ingest_document", ...],
  "required_skills": ["data_analysis", "web_scraping", ...],
  "stop_conditions": {"max_docs": 100, "coverage_threshold": 0.85}
}
"""

    def __init__(self, config, llm, skill_loader):
        self.config       = config
        self.llm          = llm
        self.skill_loader = skill_loader
    
    def make_plan(self, topic: str, pre_ingested_docs=None) -> "ResearchPlan":
        # Load all skills and include their descriptions in planning context
        all_skills = self.skill_loader.load_all()
        skills_ctx = "\n".join(f"- {s.name}: {s.description[:150]}" for s in all_skills)
        
        docs_ctx = ""
        if pre_ingested_docs:
            docs_ctx = "\n".join(
                f"- [{d.source_type.value}] {d.title}: {d.text[:200]}..."
                for d in pre_ingested_docs[:5]
            )
        
        prompt = f"""
Topic: {topic}

Available skills:
{skills_ctx or "None loaded yet"}

Pre-ingested documents:
{docs_ctx or "None"}

Return JSON research plan.
"""
        data = self.llm.json(prompt, system=self.SYSTEM_PROMPT, use_claude=True)
        
        # Activate relevant skills
        selected_skill_names = data.get("required_skills", [])
        active_skills = [s for s in all_skills if s.name in selected_skill_names]
        
        from omega_researcher.schemas import ResearchPlan
        return ResearchPlan(
            topic             = data.get("topic", topic),
            subquestions      = data.get("subquestions", []),
            queries           = data.get("queries", []),
            source_preferences = data.get("source_preferences", []),
            stop_conditions   = data.get("stop_conditions", {}),
            # NEW fields added to ResearchPlan schema:
            spawn_subagents   = data.get("spawn_subagents", False),
            subagent_topics   = data.get("subagent_topics", []),
            required_tools    = data.get("required_tools", []),
            active_skills     = active_skills,
        )
```

### 11.3 `agents/actor_agent.py`

```python
# agents/actor_agent.py (key method — full implementation in actual code)
class ActorAgent:
    """
    Executes research actions: web crawl, file ingestion, code execution,
    index lookups, and subagent spawning.
    Updates state.docs, INDEXES/, scratch_pad, rolling_summary per action.
    """
    
    async def run_cycle(self, state: ResearchState) -> ResearchState:
        """
        One PAC cycle: execute up to actor_max_actions_per_cycle actions.
        Actions are picked by calling _decide_next_action() at each step.
        """
        for _ in range(self.config.actor_max_actions_per_cycle):
            action = await self._decide_next_action(state)
            
            if action["type"] == "web_search":
                docs = await self._do_deep_search(action["query"], state)
                state.docs.extend(docs)
                for doc in docs:
                    self.index_manager.index_document(doc, state.query, self.llm, state.scratch_pad)
            
            elif action["type"] == "search_indexes":
                result = self.mcp.call_tool("search_from_indexes", {"query": action["query"]})
                self.scratch_pad.append("Index Lookups", result)
            
            elif action["type"] == "execute_code":
                result = self.mcp.call_tool("execute_python", {"code": action["code"]})
                self.scratch_pad.append("Code Results", result)
            
            elif action["type"] == "spawn_subagents":
                from omega_researcher.agents.subagent_spawner import SubagentSpawner
                spawner = SubagentSpawner(self.config, self.llm, None, self.skill_loader)
                results = await spawner.spawn_for_subquestions(
                    action["subtopics"], state
                )
                state = spawner.merge_results(state, results)
            
            elif action["type"] == "done":
                break
            
            # Always update rolling summary after each action
            self.rolling_summary.update(
                f"Action: {action['type']} | Result: {len(state.docs)} total docs",
                context=state.query
            )
        
        return state
    
    async def _decide_next_action(self, state: ResearchState) -> dict:
        """
        LLM decides what to do next based on current state.
        This is the core 'think → act' step of the Actor.
        """
        # Include active skill instructions in prompt
        skill_guidance = "\n".join(
            s.content[:500] for s in state.active_skills
        )
        
        prompt = f"""
Research query: {state.query}
PAC cycle: {state.pac_cycle}
Documents collected: {len(state.docs)}
Current rolling summary: {state.rolling_summary[-500:]}
Scratch pad (recent): {self.scratch_pad.read("Global Notes")[-300:]}
Indexed topics: {list(state.topics_json.keys())[:10]}
Remaining queries in plan: {state.plan.queries[:3]}
Active skills guidance:
{skill_guidance[:400]}

What is the best next action? Return JSON:
{{"type": "web_search"|"search_indexes"|"execute_code"|"spawn_subagents"|"done",
  "query": "..." (for web_search/search_indexes),
  "code": "..." (for execute_code — valid Python),
  "subtopics": ["..."] (for spawn_subagents),
  "reasoning": "..."
}}
"""
        return self.llm.json(
            prompt, system="You are a research actor. Pick the optimal next action.",
            use_claude=True, max_tokens=1000
        )
```

### 11.4 `agents/critic_agent.py`

```python
# agents/critic_agent.py (extended from original critic.py)
class CriticAgent:
    """
    Extended critic: per-subquestion coverage scoring, recommended actions,
    and explicit coverage threshold checking.
    """
    SYSTEM_PROMPT = """You are a rigorous research critic.
Evaluate coverage of each subquestion on a 0.0–1.0 scale.
Return JSON:
{
  "covered_subtopics": [...],
  "missing_subtopics": [...],
  "contradictions": [...],
  "followup_queries": [...],
  "should_research_more": true/false,
  "coverage_scores": {"subquestion text": 0.0-1.0, ...},
  "overall_coverage": 0.0-1.0,
  "recommended_actions": ["run_code_analysis", "search_academic", ...]
}
"""
    
    def evaluate(self, query: str, state: "ResearchState") -> "CoverageReport":
        subquestions_ctx = "\n".join(f"- {sq}" for sq in state.plan.subquestions)
        doc_summary = "\n".join(
            f"[{i+1}] {d.title}: {d.text[:150]}..."
            for i, d in enumerate(state.docs[:20])
        )
        indexed_topics = ", ".join(list(state.topics_json.keys())[:10])
        
        prompt = f"""
Query: {query}

Subquestions to evaluate:
{subquestions_ctx}

Documents collected ({len(state.docs)} total):
{doc_summary}

Indexed topics: {indexed_topics}

Rolling summary (what we know so far):
{state.rolling_summary[-600:]}

Return JSON coverage evaluation.
"""
        data = self.llm.json(prompt, system=self.SYSTEM_PROMPT, use_claude=True)
        
        from omega_researcher.schemas import CoverageReport
        return CoverageReport(
            covered_subtopics  = data.get("covered_subtopics", []),
            missing_subtopics  = data.get("missing_subtopics", []),
            contradictions     = data.get("contradictions", []),
            followup_queries   = data.get("followup_queries", []),
            should_research_more = (
                data.get("overall_coverage", 0.0) < self.config.coverage_threshold
            ),
            coverage_scores    = data.get("coverage_scores", {}),
            overall_coverage   = data.get("overall_coverage", 0.0),
            recommended_actions = data.get("recommended_actions", []),
        )
```

---

## 12. Experiences & MetaLearn System

### 12.1 `agents/meta_agent.py`

```python
# agents/meta_agent.py
"""
MetaAgent: runs in a completely SEPARATE LLM context.
Never shares conversation history with research agents.
Purpose: post-evaluation, experience logging, skill creation.
"""
from __future__ import annotations
import anthropic
from omega_researcher.memory.experiences import ExperienceLogger
from omega_researcher.skills.skill_creator import SkillCreator
from omega_researcher.config import Config
from omega_researcher.schemas import Experience, ResearchState, ResearchPlan
from datetime import datetime

class MetaAgent:
    def __init__(self, config: Config):
        self.config  = config
        self.exp_log = ExperienceLogger(config)
        # CRITICAL: MetaAgent uses its OWN fresh LLM client
        # with no shared context window from research agents
        self._client = anthropic.Anthropic(api_key=config.anthropic_api_key)
    
    async def post_eval(
        self,
        query: str,
        plan: ResearchPlan,
        report: str,
        state: ResearchState,
        duration_seconds: float,
    ) -> None:
        """
        Evaluate research quality, log experience, trigger MetaLearn if needed.
        Runs asynchronously — does NOT block the main research output.
        """
        # Fresh LLM call with no research context
        eval_result = self._evaluate(query, plan, report, state)
        
        exp = Experience(
            timestamp         = datetime.now().isoformat(),
            query             = query,
            outcome           = eval_result["outcome"],
            coverage_achieved = eval_result["coverage"],
            skills_used       = [s.name for s in state.active_skills],
            tools_used        = eval_result["tools_used"],
            what_worked       = eval_result["what_worked"],
            what_failed       = eval_result["what_failed"],
            suggestions       = eval_result["suggestions"],
            subagents_spawned = len(state.spawned_subagent_ids),
            total_docs        = len(state.docs),
            duration_seconds  = duration_seconds,
        )
        
        self.exp_log.log(exp)
        print(f"[meta_agent] Logged experience: {exp.outcome} ({exp.coverage_achieved:.0%})")
        
        # Trigger MetaLearn if enough experiences
        all_exp = self.exp_log.read_all()
        if len(all_exp) % self.config.metalear_trigger_every == 0:
            await self.meta_learn()
    
    def _evaluate(self, query, plan, report, state) -> dict:
        prompt = f"""
Evaluate this research session objectively.

Query: {query}
Planned subquestions: {plan.subquestions}
Total docs collected: {len(state.docs)}
Report excerpt (first 1000 chars): {report[:1000]}

Assess:
1. Was the query well-answered? (outcome: "success" | "partial" | "failure")
2. Coverage score 0.0-1.0
3. Which tools/approaches worked?
4. What failed or was missing?
5. Suggestions for next time this query type appears

Return JSON:
{{
  "outcome": "success|partial|failure",
  "coverage": 0.0-1.0,
  "tools_used": ["web_search", "execute_python", ...],
  "what_worked": "...",
  "what_failed": "...",
  "suggestions": "..."
}}
"""
        response = self._client.messages.create(
            model      = self.config.claude_model,
            max_tokens = self.config.meta_max_tokens,
            messages   = [{"role": "user", "content": prompt}],
        )
        from omega_researcher.llm_client import fix_json_escapes
        import json
        text = fix_json_escapes(response.content[0].text)
        return json.loads(text)
    
    async def meta_learn(self) -> None:
        """
        MetaLearn(): reads experiences.md, identifies patterns,
        creates or updates skills in SKILLS/.
        """
        from omega_researcher.llm_client import LLMClient
        from omega_researcher.config import Config
        
        # Fresh LLM client (no research context)
        llm = LLMClient(self.config)
        creator = SkillCreator(self.config, llm)
        
        failures = self.exp_log.read_failures()
        if len(failures) < self.config.metalear_min_failures:
            return
        
        # Aggregate failure patterns
        failures_text = "\n\n".join(
            f"Query type: {f.query[:100]}\n"
            f"Failure: {f.what_failed}\n"
            f"Suggestions: {f.suggestions}"
            for f in failures[-20:]  # Last 20 failures
        )
        
        prompt = f"""
Analyze these research failures and identify skill gaps.
For each distinct failure pattern, describe:
1. What type of task it represents
2. What skill would have prevented the failure
3. What that skill should teach

Failures:
{failures_text}

Return JSON:
{{
  "skill_gaps": [
    {{
      "task_type": "...",
      "skill_name": "...",
      "what_the_skill_should_contain": "...",
      "should_update_existing": true/false,
      "existing_skill_name": "..." // if should_update_existing
    }}
  ]
}}
"""
        data = llm.json(prompt, system="Analyze failure patterns. Return JSON.", use_claude=True)
        
        for gap in data.get("skill_gaps", []):
            if gap.get("should_update_existing") and gap.get("existing_skill_name"):
                creator.update_skill(gap["existing_skill_name"], gap["what_the_skill_should_contain"])
            else:
                creator.create_skill(
                    task_description = gap["task_type"],
                    what_worked      = gap["what_the_skill_should_contain"],
                    name             = gap.get("skill_name"),
                )
        
        print(f"[meta_learn] Created/updated {len(data.get('skill_gaps', []))} skills")
```

---

## 13. Enhanced Synthesizer

The synthesizer is mostly preserved from the original, but now:
- Reads `rolling_summary.md` for context
- Pulls from `scratch_pad.md` for key insights
- Uses subagent report sections as input
- Passes `state.topics_json` (which now includes subagent learnings)

```python
# synthesizer/synthesizer.py (enhanced)
class Synthesizer:
    def synthesize(self, topic: str, state: ResearchState) -> str:
        # 1. Index any remaining un-indexed docs (should be few at this point)
        indexer = Indexer(self.llm, self.config)
        # indexer is called incrementally — most docs already indexed by actor
        
        # 2. Build overviews (unchanged)
        ob = OverviewBuilder(self.llm, self.config)
        ob.build_overview(self.config.indexes_dir)
        
        # 3. Build report with full context
        rb = ReportBuilder(self.llm, self.config)
        
        # Pass rolling_summary as initial context (key enhancement)
        report = rb.build_report(
            topics_json     = state.topics_json,
            rolling_summary = state.rolling_summary,   # NEW
            scratch_pad     = state.scratch_pad,       # uses ScratchPad.read()
        )
        
        return report
```

---

## 14. LLM Client (enhanced)

### Key addition: Tool-call support

```python
# llm_client.py — add to ClaudeClient:

def with_tools(
    self,
    prompt: str,
    tools: list[dict],       # Anthropic tool definitions
    system: str = "You are a helpful research assistant.",
    max_tokens: int = 4096,
) -> tuple[str, list[dict]]:
    """
    Generate with tool use enabled.
    Returns (text_response, list_of_tool_calls).
    
    Used by ActorAgent when it needs the LLM to call MCP tools.
    """
    response = self.client.messages.create(
        model    = self.model,
        max_tokens = max_tokens,
        system   = system,
        tools    = tools,
        messages = [{"role": "user", "content": prompt}],
    )
    
    text    = ""
    tool_calls = []
    for block in response.content:
        if block.type == "text":
            text += block.text
        elif block.type == "tool_use":
            tool_calls.append({
                "name":  block.name,
                "input": block.input,
                "id":    block.id,
            })
    
    return text, tool_calls
```

---

## 15. Integration: Full Data Flow

```
INPUT
  └─ query: "Analyze the impact of LLMs on software engineering jobs,
             using the attached survey data and literature"
     file_paths: ["survey_2024.xlsx", "llm_impact_study.pdf"]

ORCHESTRATOR.__init__()
  ├─ LLMClient (MiniMax + Claude)
  ├─ ScratchPad → scratch_pad.md
  ├─ RollingSummary → rolling_summary.md
  ├─ IndexManager → INDEXES/
  ├─ SkillLoader → SKILLS/*/SKILL.md
  ├─ ExperienceLogger → experiences.md
  └─ MCP server (all tools registered)

ORCHESTRATOR.run()
  │
  ├─ [INGEST] survey_2024.xlsx → DataReader → IngestedDocument(DATA)
  │     text: schema + head(20) + describe()
  │
  ├─ [INGEST] llm_impact_study.pdf → DoclingParser → IngestedDocument(FILE)
  │     text: full markdown, tables extracted, images described
  │
  ├─ [INDEX] Both docs indexed immediately via IndexManager
  │     INDEXES/Software_Engineering/LLM_Impact/information.md ← pdf content
  │     INDEXES/Survey_Data/information.md ← excel summary
  │     scratch_pad.md updated with key facts from both files
  │
  ├─ [PLANNER] PlannerAgent.make_plan()
  │     Loads SKILLS: data_analysis (triggered by xlsx), academic_research (triggered by pdf)
  │     Plan: {
  │       subquestions: ["What does the survey data show about job displacement?",
  │                      "What do academic papers say about LLM adoption rates?",
  │                      "What mitigation strategies are proposed?"],
  │       queries: ["LLM software engineering job impact 2024",
  │                 "developer productivity AI tools survey"],
  │       spawn_subagents: true,
  │       subagent_topics: ["Job displacement statistics",
  │                         "Reskilling and mitigation strategies"],
  │       required_tools: ["execute_python", "search_from_indexes"]
  │     }
  │
  ├─ [PAC CYCLE 1]
  │   │
  │   ├─ ACTOR._decide_next_action() → {type: "execute_code"}
  │   │     (skill says: analyze tabular data first)
  │   │     Code: df.corr(), df.groupby("role").mean(), etc.
  │   │     Result → scratch_pad["Code Results"]
  │   │
  │   ├─ ACTOR._decide_next_action() → {type: "search_indexes"}
  │   │     search_from_indexes("LLM job displacement")
  │   │     Returns: INDEXES/LLM_Impact/information.md excerpt
  │   │     → confirms what pdf said, no re-fetching needed
  │   │
  │   ├─ ACTOR._decide_next_action() → {type: "spawn_subagents"}
  │   │     SubagentSpawner.spawn_for_subquestions(
  │   │       ["Job displacement statistics", "Reskilling strategies"],
  │   │       depth=1
  │   │     )
  │   │     │
  │   │     ├─ SubAgent[depth=1, topic="Job displacement statistics"]
  │   │     │     runs its own PAC loop (max_docs=30)
  │   │     │     web_searches → indexes → rolling_summary
  │   │     │     returns SubAgentResult{docs, topics_json, report_section}
  │   │     │
  │   │     └─ SubAgent[depth=1, topic="Reskilling strategies"]
  │   │           similar PAC loop
  │   │           returns SubAgentResult{...}
  │   │     
  │   │     SubagentSpawner.merge_results() → state.docs extended
  │   │     INDEXES/ updated with subagent learnings (shared dir)
  │   │
  │   ├─ ACTOR._decide_next_action() → {type: "web_search"}
  │   │     deep_search("LLM impact software engineering 2024")
  │   │     [existing crawl → fetch → extract → frontier loop]
  │   │     Every 10 docs: Critic gap check (original logic preserved)
  │   │     Each doc → IndexManager.index_document() immediately
  │   │
  │   └─ ACTOR._decide_next_action() → {type: "done"}  (5 actions reached)
  │
  ├─ [CRITIC] CriticAgent.evaluate()
  │     coverage_scores: {
  │       "Job displacement": 0.90,
  │       "Adoption rates": 0.75,
  │       "Mitigation strategies": 0.60
  │     }
  │     overall_coverage: 0.75 < 0.85 threshold
  │     followup_queries: ["developer reskilling programs AI 2024"]
  │     should_research_more: True
  │
  ├─ [PAC CYCLE 2]
  │   ACTOR → web_search("developer reskilling programs AI 2024")
  │   [more docs → indexed]
  │   CRITIC → overall_coverage: 0.88 ≥ 0.85 → should_research_more: False
  │
  ├─ [SYNTHESIZER]
  │   OverviewBuilder → traverses INDEXES/ tree, generates overview.md per dir
  │   ReportBuilder → traverses topics_json, writes each section with rolling_summary
  │   Final report → report-content.md
  │
  └─ [META-AGENT] (async, non-blocking)
        post_eval(query, plan, report, state)
        → experiences.md: logs success, coverage=0.88, skills_used=[data_analysis]
        → If 10th experience: MetaLearn() triggered
              reads failures → identifies gaps → updates/creates SKILLS
```

---

## 16. Docker & Infrastructure

### Build & Run

```bash
# Build executor image
docker build -f docker/Dockerfile.executor -t omega-executor:latest .

# Start infrastructure
docker-compose -f docker/docker-compose.yml up -d

# Verify SearxNG is running
curl http://localhost:8080/search?q=test&format=json

# Run research
python -m omega_researcher.main "How do transformer architectures scale?" \
  --files paper.pdf data.csv \
  --max-docs 80 \
  --spawn-subagents
```

### Environment (`.env`)

```bash
# LLM Providers
MINIMAX_API_KEY=your_minimax_key
MINIMAX_MODEL=MiniMax-M1
ANTHROPIC_API_KEY=your_claude_key
CLAUDE_MODEL=claude-sonnet-4-20250514

# Search
SEARXNG_BASE_URL=http://localhost:8080

# MCP
MCP_HOST=localhost
MCP_PORT=8765

# Paths (defaults fine for most uses)
INDEXES_DIR=INDEXES
SKILLS_DIR=SKILLS
```

---

## 17. Configuration Reference

| Parameter | Default | Description |
|---|---|---|
| `max_docs` | 100 | Max web-crawled documents total |
| `critique_batch_size` | 10 | Critic runs every N docs (original behavior) |
| `SPAWNING_DEPTH_LIMIT` | 3 | Max recursive subagent depth |
| `max_subagents` | 5 | Max parallel subagents per node |
| `subagent_max_docs` | 30 | Smaller doc budget per subagent |
| `coverage_threshold` | 0.85 | Critic score to stop PAC loop |
| `max_pac_cycles` | 20 | Safety cap on PAC iterations |
| `actor_max_actions_per_cycle` | 5 | Actor actions before Critic re-runs |
| `rolling_summary_max_tokens` | 2000 | Compress rolling summary at this size |
| `index_search_top_k` | 5 | `search_from_indexes()` returns top-K hits |
| `metalear_trigger_every` | 10 | MetaLearn runs every N logged experiences |
| `metalear_min_failures` | 3 | Min failures before skill update |
| `docker_executor_timeout` | 60 | Code execution timeout (seconds) |
| `docling_ocr` | True | Enable OCR for scanned PDFs |
| `max_file_size_mb` | 50 | Skip files larger than this |

---

## 18. Implementation Roadmap (Phases)

### Phase 1 — Core PAC + Docling (Week 1-2)
- [ ] Rename `deepresearch/` → `omega_researcher/`
- [ ] Expand `config.py` with all new fields
- [ ] Expand `schemas.py` with new dataclasses
- [ ] Implement `ingestion/docling_parser.py`
- [ ] Implement `ingestion/data_reader.py`
- [ ] Implement `orchestrator.py` (PAC loop skeleton)
- [ ] Refactor `planner.py` → `agents/planner_agent.py`
- [ ] Refactor `critic.py` → `agents/critic_agent.py` (with coverage scores)
- [ ] Wire existing `deep_search.py` logic into `agents/actor_agent.py`
- [ ] Update `main.py` / `cli.py` with `file_paths` argument

### Phase 2 — Memory + Skills (Week 2-3)
- [ ] Implement `memory/index_manager.py` (live index access API)
- [ ] Implement `memory/rolling_summary.py`
- [ ] Implement `memory/scratch_pad.py` (thread-safe)
- [ ] Implement `memory/experiences.py`
- [ ] Implement `search/index_search.py` (`search_from_indexes()`)
- [ ] Implement `skills/skill_loader.py`
- [ ] Implement `skills/skill_creator.py`
- [ ] Create initial SKILLS/ library (5-6 base skills)
- [ ] Integrate `IndexManager.index_document()` into actor cycle (true INDEX-AS-YOU-GO)

### Phase 3 — MCP Server + Docker (Week 3-4)
- [ ] Implement `mcp/mcp_server.py` with FastMCP
- [ ] Implement `mcp/tools/code_executor.py`
- [ ] Implement `mcp/tools/data_tools.py`
- [ ] Implement `mcp/tools/search_tools.py`
- [ ] Implement `mcp/tools/file_tools.py`
- [ ] Implement `mcp/tools/skill_tools.py`
- [ ] Create `docker/Dockerfile.executor`
- [ ] Create `docker/docker-compose.yml`
- [ ] Build and test executor image

### Phase 4 — Multi-Agent + MetaLearn (Week 4-5)
- [ ] Implement `agents/subagent_spawner.py`
- [ ] Implement `agents/meta_agent.py`
- [ ] Wire subagent spawning into actor (actor detects `spawn_subagents` from plan)
- [ ] Implement `MetaLearn()` function
- [ ] Test recursive spawning up to depth=3
- [ ] Test MetaLearn cycle (trigger at 10 experiences)

### Phase 5 — Polish & Testing (Week 5-6)
- [ ] Integration tests for full PAC loop
- [ ] Load test subagent spawning (asyncio.gather performance)
- [ ] Memory compression tests (rolling_summary)
- [ ] Create full SKILLS/ library from experiences
- [ ] Write comprehensive README
- [ ] Add `--help` to CLI with all options

---

## 19. File-by-File Implementation Guide

### Files to create from scratch

| File | Lines (est.) | Key dependencies |
|---|---|---|
| `orchestrator.py` | ~200 | All agents, MCP, memory |
| `agents/planner_agent.py` | ~100 | llm_client, skill_loader, schemas |
| `agents/actor_agent.py` | ~200 | llm_client, MCP, index_manager |
| `agents/critic_agent.py` | ~80 | llm_client, schemas |
| `agents/subagent_spawner.py` | ~150 | orchestrator, asyncio |
| `agents/meta_agent.py` | ~150 | anthropic, experiences, skill_creator |
| `ingestion/docling_parser.py` | ~120 | docling |
| `ingestion/data_reader.py` | ~100 | pandas |
| `memory/index_manager.py` | ~80 | indexer, pathlib |
| `memory/rolling_summary.py` | ~80 | llm_client |
| `memory/scratch_pad.py` | ~80 | threading, pathlib |
| `memory/experiences.py` | ~80 | json, pathlib |
| `search/index_search.py` | ~60 | pathlib |
| `skills/skill_loader.py` | ~80 | yaml, pathlib |
| `skills/skill_creator.py` | ~100 | llm_client, pathlib |
| `mcp/mcp_server.py` | ~150 | fastmcp, all tools |
| `mcp/tools/code_executor.py` | ~80 | docker |
| `mcp/tools/data_tools.py` | ~60 | data_reader |
| `mcp/tools/search_tools.py` | ~60 | searx_client, index_search |
| `mcp/tools/file_tools.py` | ~60 | docling_parser, data_reader |
| `mcp/tools/skill_tools.py` | ~60 | skill_loader, skill_creator |

### Files to migrate and enhance

| Original | New location | Changes |
|---|---|---|
| `planner.py` | `agents/planner_agent.py` | + skill loading, + subagent decision |
| `critic.py` | `agents/critic_agent.py` | + coverage scores, + recommended_actions |
| `deep_search.py` | `agents/actor_agent.py` | + tool calls, + index-as-you-go |
| `fetcher.py` | `ingestion/web_fetcher.py` | No change needed |
| `extractor.py` | `ingestion/extractor.py` | No change needed |
| `frontier.py` | `search/frontier.py` | No change needed |
| `searx_client.py` | `search/searx_client.py` | No change needed |
| `llm_client.py` | `llm_client.py` | + `with_tools()` method |
| `schemas.py` | `schemas.py` | + all new dataclasses |
| `config.py` | `config.py` | + all new fields |
| `synthesizer/indexer.py` | `synthesizer/indexer.py` | + per-doc indexing API |
| `synthesizer/synthesizer.py` | `synthesizer/synthesizer.py` | + rolling_summary, + scratch_pad |

### New requirements

```
# requirements.txt additions
docling>=2.0.0              # Document ingestion
fastmcp>=0.5.0              # MCP server
docker>=7.0.0               # Code executor
pyyaml>=6.0                 # Skill file frontmatter
scikit-learn>=1.4           # For analytics sandbox
scipy>=1.13                 # For analytics sandbox
statsmodels>=0.14           # For analytics sandbox
chromadb>=0.5.0             # (Optional Phase 2+: vector index)
tabulate>=0.9               # Markdown tables
```

---

## Summary: What makes OmegaResearcher different

| Capability | Original | OmegaResearcher |
|---|---|---|
| Input | Query string only | Query + PDF/DOCX/PPTX/HTML/CSV/Excel |
| Search | SearxNG (auto) | SearxNG (auto) + on-demand MCP tool |
| Knowledge memory | Write-only INDEXES/ | INDEX-AS-YOU-GO + `search_from_indexes()` |
| Context | None between cycles | rolling_summary + scratch_pad |
| Agents | Single thread | Multi-agent, parallel, recursive (depth≤3) |
| Code execution | None | Docker sandbox (pandas/numpy/sklearn) |
| Skills | None | Dynamic SKILLS/*/SKILL.md loading |
| Meta-learning | None | experiences.md + MetaLearn() → skill updates |
| Framework | Ad-hoc loop | Formal Planner→Actor→Critic |
| Post-eval | None | Separate MetaAgent (no context pollution) |
| Output | Report only | Report + indexed knowledge tree |
