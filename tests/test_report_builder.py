from pathlib import Path
from unittest.mock import MagicMock

import pytest

from deepresearch.config import Config
from deepresearch.synthesizer.report_builder import ReportBuilder


@pytest.fixture
def builder(tmp_path):
    config = Config(
        anthropic_api_key="test",
        workspace_dir=str(tmp_path),
        indexes_dir=str(tmp_path / "indexes"),
    )
    llm = MagicMock()
    return ReportBuilder(llm, config)


class TestDeduplicateSectionHeadings:
    def test_removes_exact_duplicate(self, builder):
        builder._emitted_headings = {"Photosynthesis"}
        content = "## Photosynthesis\nSome content.\n## Light Reactions\nMore content."
        result = builder._deduplicate_section_headings(content)
        assert "## Photosynthesis" not in result
        assert "## Light Reactions" in result
        assert "Some content." in result

    def test_removes_suffix_match(self, builder):
        builder._emitted_headings = {"Photosynthesis > Light Reactions"}
        content = "### Light Reactions\nDetails here."
        result = builder._deduplicate_section_headings(content)
        assert "### Light Reactions" not in result
        assert "Details here." in result

    def test_keeps_new_headings(self, builder):
        builder._emitted_headings = {"Photosynthesis"}
        content = "## Calvin Cycle\nNew content."
        result = builder._deduplicate_section_headings(content)
        assert "## Calvin Cycle" in result
        assert "New content." in result

    def test_empty_headings_set(self, builder):
        builder._emitted_headings = set()
        content = "## Anything\nContent."
        result = builder._deduplicate_section_headings(content)
        assert result == content

    def test_preserves_non_heading_lines(self, builder):
        builder._emitted_headings = {"Photosynthesis"}
        content = "Some intro text.\n## Photosynthesis\nContent.\nMore text."
        result = builder._deduplicate_section_headings(content)
        assert "Some intro text." in result
        assert "## Photosynthesis" not in result
        assert "Content." in result
        assert "More text." in result

    def test_multiple_duplicates_in_one_section(self, builder):
        builder._emitted_headings = {"A", "A > B", "A > C"}
        content = (
            "## A\n"
            "Intro.\n"
            "### B\n"
            "Details B.\n"
            "### C\n"
            "Details C.\n"
            "### D\n"
            "New D."
        )
        result = builder._deduplicate_section_headings(content)
        assert "## A" not in result
        assert "### B" not in result
        assert "### C" not in result
        assert "### D" in result
        assert "New D." in result

    def test_does_not_remove_partial_word_match(self, builder):
        builder._emitted_headings = {"Photo"}
        content = "## Photosynthesis\nContent."
        result = builder._deduplicate_section_headings(content)
        assert "## Photosynthesis" in result
