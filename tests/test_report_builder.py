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


class TestFindSimilarTopic:
    def test_exact_match(self, builder):
        result = builder._find_similar_topic(
            "Photosynthesis", {"Photosynthesis", "Calvin Cycle"}
        )
        assert result == "Photosynthesis"

    def test_case_insensitive_match(self, builder):
        result = builder._find_similar_topic(
            "photosynthesis", {"Photosynthesis", "Calvin Cycle"}
        )
        assert result == "Photosynthesis"

    def test_punctuation_difference(self, builder):
        result = builder._find_similar_topic(
            "Self Improving Learning Loops",
            {"Self-Improving Learning Loops", "Other Topic"},
        )
        assert result == "Self-Improving Learning Loops"

    def test_no_good_match(self, builder):
        result = builder._find_similar_topic(
            "Completely Unrelated", {"Photosynthesis", "Calvin Cycle"}
        )
        assert result is None

    def test_empty_candidates(self, builder):
        result = builder._find_similar_topic("Photosynthesis", set())
        assert result is None

    def test_threshold_too_high(self, builder):
        result = builder._find_similar_topic(
            "AI", {"Photosynthesis", "Calvin Cycle"}, threshold=0.9
        )
        assert result is None


class TestSortTopicsIntelligently:
    def test_exact_llm_response(self, builder):
        topics = {
            "Topic B": {"sub": {}},
            "Topic A": {"sub": {}},
            "Topic C": {"sub": {}},
        }
        builder.llm.json.return_value = ["Topic A", "Topic B", "Topic C"]
        result = builder._sort_topics_intelligently(topics, ["Root"])
        names = [n for n, _ in result]
        assert names == ["Topic A", "Topic B", "Topic C"]

    def test_similarity_matched_llm_response(self, builder):
        topics = {
            "Self-Improving Learning Loops": {"sub": {}},
            "Other Topic": {"sub": {}},
        }
        # LLM returns slightly misspelled name
        builder.llm.json.return_value = ["Self Improving Learning Loops", "Other Topic"]
        result = builder._sort_topics_intelligently(topics, ["Root"])
        names = [n for n, _ in result]
        assert names == ["Self-Improving Learning Loops", "Other Topic"]

    def test_low_coverage_fallback_to_original(self, builder):
        topics = {
            "Topic A": {"sub": {}},
            "Topic B": {"sub": {}},
            "Topic C": {"sub": {}},
            "Topic D": {"sub": {}},
        }
        # LLM only returns 1 valid topic out of 4 (25% < 50% threshold)
        builder.llm.json.return_value = ["Topic A"]
        result = builder._sort_topics_intelligently(topics, ["Root"])
        names = [n for n, _ in result]
        # Should fall back to original order
        assert names == ["Topic A", "Topic B", "Topic C", "Topic D"]

    def test_exception_fallback_to_original(self, builder):
        topics = {
            "Topic B": {"sub": {}},
            "Topic A": {"sub": {}},
        }
        builder.llm.json.side_effect = Exception("API Error")
        result = builder._sort_topics_intelligently(topics, ["Root"])
        names = [n for n, _ in result]
        # Should fall back to original dict order
        assert names == ["Topic B", "Topic A"]

    def test_single_topic_no_sorting(self, builder):
        topics = {"Only Topic": {"sub": {}}}
        result = builder._sort_topics_intelligently(topics, ["Root"])
        names = [n for n, _ in result]
        assert names == ["Only Topic"]

    def test_empty_subtopics_dict(self, builder):
        topics = {"Topic A": {}, "Topic B": {}}
        builder.llm.json.return_value = ["Topic B", "Topic A"]
        result = builder._sort_topics_intelligently(topics, ["Root"])
        names = [n for n, _ in result]
        assert names == ["Topic B", "Topic A"]
