from __future__ import annotations
import pytest
from deepresearch.config import Config


@pytest.fixture
def config() -> Config:
    return Config(
        searxng_base_url="http://localhost:8080",
        max_docs=10,
        critique_batch_size=5,
        fetch_timeout=5.0,
        workspace_dir="test_workspace",
        max_depth=2,
    )
