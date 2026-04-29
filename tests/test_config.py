from __future__ import annotations
import os
import pytest
from deepresearch.config import Config


def test_config_fixture(config: Config) -> None:
    assert config.max_docs == 10
    assert config.fetch_timeout == 5.0
    assert config.workspace_dir == "test_workspace"
    assert config.enable_browser is False


def test_config_from_env_uses_defaults(monkeypatch) -> None:
    # Ensure no env vars are set
    for key in os.environ:
        if key.startswith(("SEARXNG", "MINIMAX", "ANTHROPIC", "MAX_", "FETCH", "BROWSER", "SYNTHESIZER", "INDEXES", "MIN_ACCUMULATOR", "WORKSPACE", "LOG_LEVEL", "ENABLE_BROWSER")):
            monkeypatch.delenv(key, raising=False)
    cfg = Config.from_env()
    assert cfg.searxng_base_url == "http://localhost:8080"
    assert cfg.max_docs == 100
    assert cfg.enable_browser is True


def test_config_from_env_reads_env_vars(monkeypatch) -> None:
    monkeypatch.setenv("SEARXNG_BASE_URL", "http://custom:8080")
    monkeypatch.setenv("MAX_DOCS", "50")
    monkeypatch.setenv("ENABLE_BROWSER", "false")
    cfg = Config.from_env()
    assert cfg.searxng_base_url == "http://custom:8080"
    assert cfg.max_docs == 50
    assert cfg.enable_browser is False
