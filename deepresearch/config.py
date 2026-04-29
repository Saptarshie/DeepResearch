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
        kwargs = {}
        if (v := os.getenv("SEARXNG_BASE_URL")) is not None:
            kwargs["searxng_base_url"] = v
        if (v := os.getenv("MINIMAX_API_KEY")) is not None:
            kwargs["minimax_api_key"] = v
        if (v := os.getenv("MINIMAX_MODEL")) is not None:
            kwargs["minimax_model"] = v
        if (v := os.getenv("ANTHROPIC_BASE_URL")) is not None:
            kwargs["anthropic_base_url"] = v
        if (v := os.getenv("ANTHROPIC_API_KEY")) is not None:
            kwargs["anthropic_api_key"] = v
        if (v := os.getenv("MAX_DOCS")) is not None:
            kwargs["max_docs"] = int(v)
        if (v := os.getenv("CRITIQUE_BATCH_SIZE")) is not None:
            kwargs["critique_batch_size"] = int(v)
        if (v := os.getenv("FETCH_TIMEOUT")) is not None:
            kwargs["fetch_timeout"] = float(v)
        if (v := os.getenv("BROWSER_WAIT_MS")) is not None:
            kwargs["browser_wait_ms"] = int(v)
        if (v := os.getenv("MAX_TOKENS")) is not None:
            kwargs["max_tokens"] = int(v)
        if (v := os.getenv("SYNTHESIZER_MAX_TOKENS")) is not None:
            kwargs["synthesizer_max_tokens"] = int(v)
        if (v := os.getenv("MAX_INDEXER_DEPTH")) is not None:
            kwargs["max_indexer_depth"] = int(v)
        if (v := os.getenv("INDEXES_DIR")) is not None:
            kwargs["indexes_dir"] = v
        if (v := os.getenv("MIN_ACCUMULATOR_THRESHOLD")) is not None:
            kwargs["min_accumulator_threshold"] = int(v)
        if (v := os.getenv("WORKSPACE_DIR")) is not None:
            kwargs["workspace_dir"] = v
        if (v := os.getenv("MAX_DEPTH")) is not None:
            kwargs["max_depth"] = int(v)
        if (v := os.getenv("MIN_CONTENT_LENGTH")) is not None:
            kwargs["min_content_length"] = int(v)
        if (v := os.getenv("LOG_LEVEL")) is not None:
            kwargs["log_level"] = v
        if (v := os.getenv("ENABLE_BROWSER")) is not None:
            kwargs["enable_browser"] = v.lower() in ("true", "1", "yes")
        return cls(**kwargs)
