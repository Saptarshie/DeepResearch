from __future__ import annotations
import pytest
from deepresearch.config import Config


@pytest.fixture
def config() -> Config:
    return Config(
        searxng_base_url="http://localhost:8080",
        anthropic_base_url="https://api.test.io/anthropic",
        anthropic_api_key="",
        anthropic_model="test-anthropic-model",
        openai_api_key="",
        openai_model="test-openai-model",
        openai_base_url="https://api.test.io/openai",
        default_provider="anthropic",
        max_docs=10,
        critique_batch_size=5,
        fetch_timeout=5.0,
        browser_wait_ms=500,
        max_tokens=1024,
        synthesizer_max_tokens=2048,
        max_indexer_depth=2,
        indexes_dir="test_indexes",
        min_accumulator_threshold=100,
        workspace_dir="test_workspace",
        max_depth=2,
        min_content_length=100,
        log_level="DEBUG",
        enable_browser=False,
    )
