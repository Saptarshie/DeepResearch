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
        _env_map = {
            "SEARXNG_BASE_URL": ("searxng_base_url", str),
            "MINIMAX_API_KEY": ("minimax_api_key", str),
            "MINIMAX_MODEL": ("minimax_model", str),
            "ANTHROPIC_BASE_URL": ("anthropic_base_url", str),
            "ANTHROPIC_API_KEY": ("anthropic_api_key", str),
            "MAX_DOCS": ("max_docs", int),
            "CRITIQUE_BATCH_SIZE": ("critique_batch_size", int),
            "FETCH_TIMEOUT": ("fetch_timeout", float),
            "BROWSER_WAIT_MS": ("browser_wait_ms", int),
            "MAX_TOKENS": ("max_tokens", int),
            "SYNTHESIZER_MAX_TOKENS": ("synthesizer_max_tokens", int),
            "MAX_INDEXER_DEPTH": ("max_indexer_depth", int),
            "INDEXES_DIR": ("indexes_dir", str),
            "MIN_ACCUMULATOR_THRESHOLD": ("min_accumulator_threshold", int),
            "WORKSPACE_DIR": ("workspace_dir", str),
            "MAX_DEPTH": ("max_depth", int),
            "MIN_CONTENT_LENGTH": ("min_content_length", int),
            "LOG_LEVEL": ("log_level", str),
            "ENABLE_BROWSER": ("enable_browser", lambda v: v.lower() in ("true", "1", "yes")),
        }
        kwargs = {}
        for env_var, (field_name, converter) in _env_map.items():
            if (v := os.getenv(env_var)) is not None:
                kwargs[field_name] = converter(v)
        return cls(**kwargs)
