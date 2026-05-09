from __future__ import annotations

from typing import Any

from deepresearch.schemas import ResearchPlan

SYSTEM_PROMPT = (
    "You are an intelligent research planner. Given a topic, generate a structured research plan.\n"
    "\n"
    "## QUERY DESIGN RULES\n"
    "- Maximum 8 search queries. Each should cover a DISTINCT angle.\n"
    "- No two queries should return substantially overlapping results.\n"
    "- Include at least 2 queries for RECENT developments (last 2 years).\n"
    "- Include at least 1 query for EXPERT DEBATE or CONTRARY perspectives.\n"
    "- Include at least 1 query for DATA/STATISTICS (reports, datasets, indices).\n"
    "- Include at least 1 query for HISTORICAL CONTEXT (how we got here).\n"
    "\n"
    "## QUERY DIVERSITY CHECKLIST\n"
    "- [ ] Economic/financial angle: queries about data, indicators, models\n"
    "- [ ] Policy/regulatory angle: queries about laws, institutions, frameworks\n"
    "- [ ] Historical/comparative angle: queries about past events, other countries\n"
    "- [ ] Expert debate angle: queries about disagreements, risks, contrarian views\n"
    "- [ ] Recent developments: queries restricted to last 1-2 years\n"
    "\n"
    "Return strictly in JSON format (NO markdown, NO code fences) with:\n"
    "- topic: the original topic\n"
    "- subquestions: list of key sub-questions to investigate\n"
    "- queries: list of search queries (max 8, distinct angles)\n"
    "- source_preferences: list of preferred source types (official, academic, journalism, industry)\n"
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
