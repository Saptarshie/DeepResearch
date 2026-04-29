from __future__ import annotations
import os
from dataclasses import dataclass


@dataclass
class Config:
    searxng_base_url: str = "http://localhost:8080"
    minimax_api_key: str = ""
    minimax_model: str = "MiniMax-M2.7"
    anthropic_base_url: str = "https://api.minimax.io/anthropic"
    anthropic_api_key: str = ""
    max_docs: int = 100
    critique_batch_size: int = 10
    fetch_timeout: float = 20.0
    browser_wait_ms: int = 2000
    max_tokens: int = 16384
    synthesizer_max_tokens: int = 100000
    max_indexer_depth: int = 3
    indexes_dir: str = "INDEXES"
    min_accumulator_threshold: int = 400
    workspace_dir: str = "workspace"
    max_depth: int = 2
    min_content_length: int = 500
    log_level: str = "INFO"
    enable_browser: bool = True

    @classmethod
    def from_env(cls) -> Config:
        return cls(
            searxng_base_url=os.getenv("SEARXNG_BASE_URL", "http://localhost:8080"),
            minimax_api_key=os.getenv("MINIMAX_API_KEY", ""),
            minimax_model=os.getenv("MINIMAX_MODEL", "MiniMax-M2.7"),
            anthropic_base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.minimax.io/anthropic"),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", ""),
        )
