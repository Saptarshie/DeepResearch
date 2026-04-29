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
    env_vars = [
        "SEARXNG_BASE_URL", "MINIMAX_API_KEY", "MINIMAX_MODEL",
        "ANTHROPIC_BASE_URL", "ANTHROPIC_API_KEY", "MAX_DOCS",
        "CRITIQUE_BATCH_SIZE", "FETCH_TIMEOUT", "BROWSER_WAIT_MS",
        "MAX_TOKENS", "SYNTHESIZER_MAX_TOKENS", "MAX_INDEXER_DEPTH",
        "INDEXES_DIR", "MIN_ACCUMULATOR_THRESHOLD", "WORKSPACE_DIR",
        "MAX_DEPTH", "MIN_CONTENT_LENGTH", "LOG_LEVEL", "ENABLE_BROWSER",
    ]
    for var in env_vars:
        monkeypatch.delenv(var, raising=False)
    assert Config.from_env() == Config()


def test_config_from_env_reads_typed_values(monkeypatch) -> None:
    monkeypatch.setenv("SEARXNG_BASE_URL", "http://custom:8080")
    monkeypatch.setenv("MAX_DOCS", "50")
    monkeypatch.setenv("FETCH_TIMEOUT", "15.5")
    cfg = Config.from_env()
    assert cfg.searxng_base_url == "http://custom:8080"
    assert cfg.max_docs == 50
    assert cfg.fetch_timeout == 15.5


def test_config_from_env_parses_truthy_booleans(monkeypatch) -> None:
    for value in ("true", "1", "yes", "TRUE", " True "):
        monkeypatch.setenv("ENABLE_BROWSER", value)
        cfg = Config.from_env()
        assert cfg.enable_browser is True, f"failed for {value!r}"


def test_config_from_env_parses_falsy_booleans(monkeypatch) -> None:
    for value in ("false", "0", "no", "FALSE", "False", "random"):
        monkeypatch.setenv("ENABLE_BROWSER", value)
        cfg = Config.from_env()
        assert cfg.enable_browser is False, f"failed for {value!r}"
