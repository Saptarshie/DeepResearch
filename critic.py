from __future__ import annotations
from deepresearch.schemas import GapReport

SYSTEM_PROMPT = """You are a research critic evaluating coverage of a research question.
[Answer strictly in JSON format (DONT include anything else ...otherwise parsing will FAIL)]
Given the original question and a set of collected documents, identify:
- covered_subtopics: what has been well answered
- missing_subtopics: what is still weak or missing
- contradictions: sources that conflict
- followup_queries: new search queries to fill gaps
- should_research_more: boolean, true if gaps remain
"""


class Critic:
    def __init__(self, llm_client):
        self.llm = llm_client

    def find_gaps(self, question: str, docs: list[dict]) -> GapReport:
        doc_summary = f"Total documents: {len(docs)}\n"
        for i, d in enumerate(docs[:20]):
            doc_summary += f"[{i + 1}] {d.get('title', 'untitled')} - {d.get('text', '')[:200]}...\n"

        prompt = (
            f"""Question: {question}\n\n{doc_summary}\n\nReturn JSON gap analysis."""
        )
        data = self.llm.json(prompt, system=SYSTEM_PROMPT, use_claude=True)
        return GapReport(
            covered_subtopics=data.get("covered_subtopics", []),
            missing_subtopics=data.get("missing_subtopics", []),
            contradictions=data.get("contradictions", []),
            followup_queries=data.get("followup_queries", []),
            should_research_more=data.get("should_research_more", False),
        )
