from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from deepresearch.planner import Planner
from deepresearch.schemas import ResearchPlan


def test_make_plan_validates_missing_keys() -> None:
    mock_llm = MagicMock()
    mock_llm.json.return_value = {"topic": "test"}  # missing queries and subquestions
    planner = Planner(mock_llm)
    with pytest.raises(ValueError, match="missing required keys"):
        planner.make_plan("test topic")


def test_make_plan_returns_plan_on_valid_response() -> None:
    mock_llm = MagicMock()
    mock_llm.json.return_value = {
        "topic": "test",
        "queries": ["q1"],
        "subquestions": ["sq1"],
        "source_preferences": ["official"],
        "stop_conditions": {"max_docs": 50},
    }
    planner = Planner(mock_llm)
    plan = planner.make_plan("test topic")
    assert isinstance(plan, ResearchPlan)
    assert plan.topic == "test"
    assert plan.queries == ["q1"]
    assert plan.subquestions == ["sq1"]
    assert plan.source_preferences == ["official"]
    assert plan.stop_conditions == {"max_docs": 50}


def test_make_plan_validates_partial_missing_keys() -> None:
    mock_llm = MagicMock()
    mock_llm.json.return_value = {"topic": "test", "queries": ["q1"]}  # missing subquestions
    planner = Planner(mock_llm)
    with pytest.raises(ValueError, match="missing required keys"):
        planner.make_plan("test topic")


def test_make_plan_uses_input_topic_when_missing() -> None:
    mock_llm = MagicMock()
    mock_llm.json.return_value = {
        "queries": ["q1"],
        "subquestions": ["sq1"],
    }
    planner = Planner(mock_llm)
    plan = planner.make_plan("fallback topic")
    assert plan.topic == "fallback topic"
