from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from deepresearch.config import Config
from deepresearch.synthesizer.overview_builder import OverviewBuilder


def test_overview_builder_skips_llm_for_leaf_nodes(tmp_path: Path) -> None:
    cfg = Config(anthropic_api_key="fake", anthropic_model="fake")
    llm = MagicMock()
    ob = OverviewBuilder(llm, cfg)
    (tmp_path / "leaf").mkdir()
    (tmp_path / "leaf" / "information.md").write_text("leaf info")
    result = ob.build_overview(tmp_path / "leaf")
    assert "leaf info" in result
    llm.generate.assert_not_called()


def test_overview_builder_calls_llm_only_at_root(tmp_path: Path) -> None:
    cfg = Config(anthropic_api_key="fake", anthropic_model="fake")
    llm = MagicMock()
    llm.generate.return_value = "root overview"
    ob = OverviewBuilder(llm, cfg)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "information.md").write_text("sub info")
    result = ob.build_overview(tmp_path)
    assert result == "root overview"
    llm.generate.assert_called_once()


def test_overview_builder_concatenates_intermediate_nodes(tmp_path: Path) -> None:
    cfg = Config(anthropic_api_key="fake", anthropic_model="fake")
    llm = MagicMock()
    ob = OverviewBuilder(llm, cfg)
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "information.md").write_text("sub info")
    # Call on subdir (is_root=False) — should concat, no LLM
    result = ob.build_overview(tmp_path / "sub", is_root=False)
    assert "sub info" in result
    llm.generate.assert_not_called()
