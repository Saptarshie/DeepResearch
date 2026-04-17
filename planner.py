from __future__ import annotations
from deepresearch.schemas import ResearchPlan

SYSTEM_PROMPT = """You are a INTELLIGENT AND HARDWORKING research planner. Given a topic, generate a structured research plan.
Return strictly in JSON format (DONT include anything else ...otherwise parsing will FAIL) with:
- topic: the original topic
- subquestions: list of key sub-questions to investigate
- queries: list of search queries to find relevant sources
- source_preferences: list of preferred source types (official, academic, journalism, industry)
- stop_conditions: object with max_docs, coverage_threshold
"""


class Planner:
    def __init__(self, llm_client):
        self.llm = llm_client

    def make_plan(self, topic: str) -> ResearchPlan:
        prompt = f"""Topic: {topic}\n\nReturn JSON plan."""
        data = self.llm.json(prompt, system=SYSTEM_PROMPT)
        return ResearchPlan(
            topic=data.get("topic", topic),
            subquestions=data.get("subquestions", []),
            queries=data.get("queries", []),
            source_preferences=data.get("source_preferences", []),
            stop_conditions=data.get(
                "stop_conditions", {"max_docs": 100, "coverage_threshold": 0.8}
            ),
        )
