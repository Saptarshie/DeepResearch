"""PlannerAgent — skill-aware research planning with subagent decision."""
from __future__ import annotations
from omega_researcher.schemas import ResearchPlan, Skill

SYSTEM_PROMPT = """You are an expert research strategist.
Given a research query, available skills, and any pre-ingested document summaries:
1. Generate a structured research plan
2. Decide if subquestions should be researched by parallel sub-agents
3. Identify which MCP tools will be needed

Return ONLY valid JSON (no extra text, no markdown fences):
{
  "topic": "...",
  "subquestions": ["...", "..."],
  "queries": ["...", "..."],
  "source_preferences": ["academic", "official", "journalism"],
  "spawn_subagents": false,
  "subagent_topics": [],
  "required_tools": ["web_search"],
  "required_skills": ["web_scraping"],
  "stop_conditions": {"max_docs": 100, "coverage_threshold": 0.85}
}"""


class PlannerAgent:
    """Generates a ResearchPlan enriched with skill context and subagent decisions."""

    def __init__(self, config, llm, skill_loader):
        self.config = config
        self.llm = llm
        self.skill_loader = skill_loader

    def make_plan(self, topic: str, pre_ingested_docs=None) -> ResearchPlan:
        """Build research plan with skill awareness."""
        all_skills = self.skill_loader.load_all()
        skills_ctx = "\n".join(
            f"- {s.name}: {s.description[:150]}" for s in all_skills
        ) or "None loaded yet"

        docs_ctx = "None"
        if pre_ingested_docs:
            docs_ctx = "\n".join(
                f"- [{d.source_type.value}] {d.title}: {d.text[:200]}..."
                for d in pre_ingested_docs[:5]
            )

        prompt = f"""Topic: {topic}

Available skills:
{skills_ctx}

Pre-ingested documents:
{docs_ctx}

Return JSON research plan."""

        try:
            data = self.llm.json(prompt, system=SYSTEM_PROMPT, use_claude=True)
        except Exception as e:
            print(f"[planner] LLM failed, using minimal plan: {e}")
            data = {}

        # Resolve active skills
        selected_skill_names = data.get("required_skills", [])
        active_skills: list[Skill] = [
            s for s in all_skills if s.name in selected_skill_names
        ]

        return ResearchPlan(
            topic=data.get("topic", topic),
            subquestions=data.get("subquestions", []),
            queries=data.get("queries", [topic]),
            source_preferences=data.get("source_preferences", []),
            stop_conditions=data.get("stop_conditions", {"max_docs": self.config.max_docs}),
            spawn_subagents=data.get("spawn_subagents", False),
            subagent_topics=data.get("subagent_topics", []),
            required_tools=data.get("required_tools", ["web_search"]),
            active_skills=active_skills,
        )
