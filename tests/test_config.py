from __future__ import annotations
from deepresearch.config import Config


def test_config_fixture(config: Config) -> None:
    assert config.max_docs == 10
    assert config.fetch_timeout == 5.0
    assert config.workspace_dir == "test_workspace"
    assert config.enable_browser is False
