from __future__ import annotations
import pytest
from unittest.mock import MagicMock
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
    }
    planner = Planner(mock_llm)
    plan = planner.make_plan("test topic")
    assert isinstance(plan, ResearchPlan)
    assert plan.queries == ["q1"]
