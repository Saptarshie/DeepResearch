from __future__ import annotations
import pytest
from unittest.mock import MagicMock
from deepresearch.critic import Critic
from deepresearch.schemas import GapReport


def test_find_gaps_validates_missing_keys() -> None:
    mock_llm = MagicMock()
    mock_llm.json.return_value = {"covered_subtopics": ["a"]}  # missing others
    critic = Critic(mock_llm)
    with pytest.raises(ValueError, match="missing required keys"):
        critic.find_gaps("question", [])


def test_find_gaps_returns_gap_report() -> None:
    mock_llm = MagicMock()
    mock_llm.json.return_value = {
        "covered_subtopics": ["a"],
        "missing_subtopics": ["b"],
        "contradictions": [],
        "followup_queries": ["q1"],
        "should_research_more": True,
    }
    critic = Critic(mock_llm)
    report = critic.find_gaps("question", [])
    assert isinstance(report, GapReport)
    assert report.should_research_more is True
