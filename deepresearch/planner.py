from __future__ import annotations

from typing import Any

from deepresearch.schemas import ResearchPlan

SYSTEM_PROMPT = (
    "You are an INTELLIGENT AND HARDWORKING research planner. Given a topic, "
    "generate a structured research plan.\n"
    "Return strictly in JSON format (DONT include anything else ...otherwise "
    "parsing will FAIL) with:\n"
    "- topic: the original topic\n"
    "- subquestions: list of key sub-questions to investigate\n"
    "- queries: list of search queries to find relevant sources\n"
    "- source_preferences: list of preferred source types (official, academic, "
    "journalism, industry)\n"
    "- stop_conditions: object with max_docs, coverage_threshold\n"
)


class Planner:
    """Generates and validates a research plan using an LLM."""

    def __init__(self, llm_client: Any) -> None:
        self.llm = llm_client

    def make_plan(self, topic: str) -> ResearchPlan:
        """Generate a research plan for the given topic.

        Raises:
            ValueError: If the LLM response is missing required keys.
        """
        prompt = f"""Topic: {topic}\n\nReturn JSON plan."""
        data = self.llm.json(prompt, system=SYSTEM_PROMPT)
        required_keys = {"queries", "subquestions"}
        missing = required_keys - set(data.keys())
        if missing:
            raise ValueError(f"LLM plan response missing required keys: {missing}")
        kwargs: dict[str, Any] = {
            "topic": data.get("topic", topic),
            "subquestions": data.get("subquestions", []),
            "queries": data.get("queries", []),
            "source_preferences": data.get("source_preferences", []),
        }
        if "stop_conditions" in data:
            kwargs["stop_conditions"] = data["stop_conditions"]
        return ResearchPlan(**kwargs)
