"""OmegaResearcher Configuration — all tunables in one place."""
from __future__ import annotations
import os
from dataclasses import dataclass
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
    max_docs: int               = 100
    critique_batch_size: int    = 10
    fetch_timeout: float        = 20.0
    browser_wait_ms: int        = 2000

    # ─── LLM Token Limits ────────────────────────────────────────────────
    max_tokens: int             = 16384
    synthesizer_max_tokens: int = 100000
    meta_max_tokens: int        = 8192

    # ─── Indexing ────────────────────────────────────────────────────────
    max_indexer_depth: int      = 3
    indexes_dir: str            = "INDEXES"
    skills_dir: str             = "SKILLS"

    # ─── Memory ──────────────────────────────────────────────────────────
    scratch_pad_path: str       = "scratch_pad.md"
    rolling_summary_path: str   = "rolling_summary.md"
    experiences_path: str       = "experiences.md"
    rolling_summary_max_tokens: int = 2000
    index_search_top_k: int     = 5

    # ─── Multi-Agent ─────────────────────────────────────────────────────
    SPAWNING_DEPTH_LIMIT: int   = 3
    max_subagents: int          = 5
    subagent_max_docs: int      = 30
    subagent_timeout: int       = 300

    # ─── MCP / Code Executor ─────────────────────────────────────────────
    mcp_host: str               = "localhost"
    mcp_port: int               = 8765
    docker_executor_image: str  = "omega-executor:latest"
    docker_executor_timeout: int = 60
    docker_network: str         = "omega_net"

    # ─── Docling ─────────────────────────────────────────────────────────
    docling_ocr: bool           = True
    docling_table_mode: str     = "accurate"
    max_file_size_mb: int       = 50

    # ─── MetaLearn ───────────────────────────────────────────────────────
    metalear_trigger_every: int = 10
    metalear_min_failures: int  = 3

    # ─── PAC Loop ────────────────────────────────────────────────────────
    coverage_threshold: float   = 0.85
    max_pac_cycles: int         = 20
    actor_max_actions_per_cycle: int = 5
