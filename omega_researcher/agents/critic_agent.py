"""CriticAgent — per-subquestion coverage scoring."""
from __future__ import annotations
from omega_researcher.schemas import CoverageReport, ResearchState

SYSTEM_PROMPT = """You are a rigorous research critic.
Evaluate coverage of each subquestion on a 0.0-1.0 scale.
Return ONLY valid JSON (no markdown fences):
{
  "covered_subtopics": ["..."],
  "missing_subtopics": ["..."],
  "contradictions": ["..."],
  "followup_queries": ["..."],
  "should_research_more": true,
  "coverage_scores": {"subquestion text": 0.0},
  "overall_coverage": 0.0,
  "recommended_actions": ["web_search", "execute_python"]
}"""


class CriticAgent:
    """Evaluates research coverage and returns structured gap report."""

    def __init__(self, config, llm):
        self.config = config
        self.llm = llm

    def evaluate(self, query: str, state: ResearchState) -> CoverageReport:
        subquestions_ctx = "\n".join(
            f"- {sq}" for sq in state.plan.subquestions
        ) or "- (no subquestions defined)"

        doc_summary = f"Total documents: {len(state.docs)}\n"
        doc_summary += "\n".join(
            f"[{i+1}] {d.title} ({d.source_type.value}): {d.text[:150]}..."
            for i, d in enumerate(state.docs[:20])
        )

        indexed_topics = ", ".join(
            list(state.topics_json.keys())[:10]
        ) or "none yet"

        rolling_ctx = state.rolling_summary[-600:] if state.rolling_summary else "none"

        prompt = f"""Query: {query}

Subquestions to evaluate:
{subquestions_ctx}

Documents collected ({len(state.docs)} total):
{doc_summary}

Indexed topics: {indexed_topics}

Rolling summary (what we know so far):
{rolling_ctx}

Return JSON coverage evaluation."""

        try:
            data = self.llm.json(prompt, system=SYSTEM_PROMPT, use_claude=True)
        except Exception as e:
            print(f"[critic] LLM failed: {e}")
            data = {}

        overall = float(data.get("overall_coverage", 0.0))
        should_more = data.get(
            "should_research_more",
            overall < self.config.coverage_threshold,
        )

        return CoverageReport(
            covered_subtopics=data.get("covered_subtopics", []),
            missing_subtopics=data.get("missing_subtopics", []),
            contradictions=data.get("contradictions", []),
            followup_queries=data.get("followup_queries", []),
            should_research_more=bool(should_more),
            coverage_scores=data.get("coverage_scores", {}),
            overall_coverage=overall,
            recommended_actions=data.get("recommended_actions", []),
        )
