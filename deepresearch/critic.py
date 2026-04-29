from __future__ import annotations

import dataclasses
import logging
from typing import Any

from deepresearch.schemas import GapReport

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a research critic evaluating coverage of a research question.
[Answer strictly in JSON format (DONT include anything else ...otherwise parsing will FAIL)]
Given the original question and a set of collected documents, identify:
- covered_subtopics: what has been well answered
- missing_subtopics: what is still weak or missing
- contradictions: sources that conflict
- followup_queries: new search queries to fill gaps
- should_research_more: boolean, true if gaps remain

Return strictly JSON with these exact keys:
- covered_subtopics (list of strings)
- missing_subtopics (list of strings)
- contradictions (list of strings)
- followup_queries (list of strings)
- should_research_more (boolean)
"""


class Critic:
    def __init__(self, llm_client: Any) -> None:
        self.llm = llm_client

    def find_gaps(self, question: str, docs: list[dict[str, Any]]) -> GapReport:
        doc_summary = f"Total documents: {len(docs)}\n"
        for i, d in enumerate(docs[:20]):
            text_preview = d.get("text", "")[:200]
            doc_summary += f"[{i + 1}] {d.get('title', 'untitled')} - {text_preview}...\n"

        prompt = (
            f"""Question: {question}\n\n{doc_summary}\n\nReturn JSON gap analysis."""
        )
        data = self.llm.json(prompt, system=SYSTEM_PROMPT, use_claude=True)
        required_keys = {f.name for f in dataclasses.fields(GapReport)}
        missing = required_keys - set(data.keys())
        if missing:
            logger.warning("LLM critic response missing required keys: %s", missing)
            raise ValueError(f"LLM critic response missing required keys: {missing}")
        return GapReport(
            covered_subtopics=data.get("covered_subtopics", []),
            missing_subtopics=data.get("missing_subtopics", []),
            contradictions=data.get("contradictions", []),
            followup_queries=data.get("followup_queries", []),
            should_research_more=data.get("should_research_more", False),
        )
