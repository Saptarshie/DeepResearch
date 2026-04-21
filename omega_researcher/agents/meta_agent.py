"""MetaAgent — separate LLM context for post-eval, experience logging, MetaLearn."""
from __future__ import annotations
import asyncio
import json
from datetime import datetime
from omega_researcher.config import Config
from omega_researcher.memory.experiences import ExperienceLogger
from omega_researcher.skills.skill_creator import SkillCreator
from omega_researcher.schemas import Experience, ResearchState, ResearchPlan


class MetaAgent:
    """
    Runs completely separately from research agents — no shared LLM context.
    Purpose: post-evaluation, experience logging, skill creation via MetaLearn.
    """

    def __init__(self, config: Config):
        self.config = config
        self.exp_log = ExperienceLogger(config)

        # CRITICAL: fresh Anthropic client — no shared context with research agents
        import anthropic
        self._client = anthropic.Anthropic(api_key=config.anthropic_api_key) if config.anthropic_api_key else None

    async def post_eval(
        self,
        query: str,
        plan: ResearchPlan,
        report: str,
        state: ResearchState,
        duration_seconds: float,
    ) -> None:
        """
        Evaluate research quality, log experience, trigger MetaLearn if needed.
        Runs asynchronously — does NOT block the main research output.
        """
        if not self._client:
            print("[meta_agent] No API key — skipping post-eval")
            return

        try:
            eval_result = await asyncio.get_event_loop().run_in_executor(
                None, self._evaluate, query, plan, report, state
            )
        except Exception as e:
            print(f"[meta_agent] Evaluation failed: {e}")
            eval_result = {
                "outcome": "partial",
                "coverage": 0.5,
                "tools_used": ["web_search"],
                "what_worked": "research completed",
                "what_failed": f"post-eval error: {e}",
                "suggestions": "check logs",
            }

        exp = Experience(
            timestamp=datetime.now().isoformat(),
            query=query,
            outcome=eval_result.get("outcome", "partial"),
            coverage_achieved=float(eval_result.get("coverage", 0.5)),
            skills_used=[s.name for s in state.active_skills],
            tools_used=eval_result.get("tools_used", []),
            what_worked=eval_result.get("what_worked", ""),
            what_failed=eval_result.get("what_failed", ""),
            suggestions=eval_result.get("suggestions", ""),
            subagents_spawned=len(state.spawned_subagent_ids),
            total_docs=len(state.docs),
            duration_seconds=duration_seconds,
        )

        self.exp_log.log(exp)
        print(f"[meta_agent] Logged experience: {exp.outcome} ({exp.coverage_achieved:.0%})")

        # Trigger MetaLearn every N experiences
        total = self.exp_log.count()
        if total > 0 and total % self.config.metalear_trigger_every == 0:
            print(f"[meta_agent] Triggering MetaLearn at {total} experiences")
            asyncio.create_task(self.meta_learn())

    def _evaluate(self, query, plan, report, state) -> dict:
        """Fresh LLM call — no research context shared."""
        prompt = f"""Evaluate this research session objectively.

Query: {query}
Planned subquestions: {plan.subquestions[:5]}
Total docs collected: {len(state.docs)}
PAC cycles run: {state.pac_cycle}
Report excerpt (first 800 chars): {report[:800]}

Assess:
1. Was the query well-answered? (outcome: "success" | "partial" | "failure")
2. Coverage score 0.0-1.0
3. Which tools/approaches worked?
4. What failed or was missing?
5. Suggestions for next time

Return ONLY valid JSON:
{{
  "outcome": "success",
  "coverage": 0.8,
  "tools_used": ["web_search"],
  "what_worked": "...",
  "what_failed": "...",
  "suggestions": "..."
}}"""

        response = self._client.messages.create(
            model=self.config.claude_model,
            max_tokens=self.config.meta_max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )

        from omega_researcher.llm_client import fix_json_escapes
        text = fix_json_escapes(response.content[0].text)
        return json.loads(text)

    async def meta_learn(self) -> None:
        """
        MetaLearn(): reads failure experiences, identifies skill gaps,
        creates or updates SKILLS/*.
        """
        from omega_researcher.llm_client import LLMClient

        failures = self.exp_log.read_failures()
        if len(failures) < self.config.metalear_min_failures:
            print(f"[meta_learn] Only {len(failures)} failures, need {self.config.metalear_min_failures}")
            return

        # Use a fresh LLM client
        llm = LLMClient(self.config)
        creator = SkillCreator(self.config, llm)

        failures_text = "\n\n".join(
            f"Query type: {f.query[:100]}\nFailure: {f.what_failed}\nSuggestions: {f.suggestions}"
            for f in failures[-20:]
        )

        prompt = f"""Analyze these research failures and identify skill gaps.

Failures:
{failures_text}

Return ONLY valid JSON:
{{
  "skill_gaps": [
    {{
      "task_type": "...",
      "skill_name": "snake_case_name",
      "what_the_skill_should_contain": "...",
      "should_update_existing": false,
      "existing_skill_name": ""
    }}
  ]
}}"""

        try:
            data = llm.json(
                prompt,
                system="Analyze failure patterns. Return JSON skill gaps.",
                use_claude=True,
            )

            for gap in data.get("skill_gaps", []):
                if gap.get("should_update_existing") and gap.get("existing_skill_name"):
                    creator.update_skill(gap["existing_skill_name"], gap["what_the_skill_should_contain"])
                else:
                    creator.create_skill(
                        task_description=gap.get("task_type", ""),
                        what_worked=gap.get("what_the_skill_should_contain", ""),
                        name=gap.get("skill_name"),
                    )

            print(f"[meta_learn] Created/updated {len(data.get('skill_gaps', []))} skills")

        except Exception as e:
            print(f"[meta_learn] Failed: {e}")
