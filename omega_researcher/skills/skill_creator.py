"""Skill creator — create/update SKILLS/*/SKILL.md from observations."""
from __future__ import annotations
from pathlib import Path
from omega_researcher.config import Config


class SkillCreator:
    """
    Create or update skill files from task observations.
    Called by the Actor for novel task types, or by MetaAgent after analyzing experiences.
    """

    def __init__(self, config: Config, llm):
        self.skills_dir = Path(config.skills_dir)
        self.llm = llm

    def create_skill(
        self,
        task_description: str,
        what_worked: str,
        name: str | None = None,
    ) -> str:
        """
        Generate a new SKILL.md from observations about what worked.
        Returns the path of the created skill file.
        """
        prompt = f"""
You are creating a reusable skill file for a research agent system.

A skill file documents HOW to handle a particular type of research task.
It includes: when to use the skill, what tools to call, prompting guidance, pitfalls.

Task type encountered:
{task_description}

What worked during this task:
{what_worked}

Generate a complete SKILL.md in this exact format:
---
name: <snake_case_name>
description: <2-3 sentence description of when to activate this skill>
tags: [<comma, separated, tags>]
version: 1.0
---

# <Skill Title>

## When to activate this skill
<bullet list of trigger conditions>

## Recommended tool sequence
<numbered steps>

## Prompting guidance
<how to prompt the LLM for this task type>

## Common pitfalls to avoid
<bullet list>
"""
        skill_content = self.llm.generate(
            prompt,
            system="Generate a concise, actionable SKILL.md file. No extra commentary.",
            max_tokens=2000,
        )

        # Extract name from YAML frontmatter
        skill_name = name or "custom_skill"
        parts = skill_content.split("---", 2)
        if len(parts) >= 3:
            try:
                import yaml
                meta = yaml.safe_load(parts[1]) or {}
                skill_name = meta.get("name", skill_name)
            except Exception:
                pass

        skill_dir = self.skills_dir / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(skill_content, encoding="utf-8")

        print(f"[skill_creator] Created skill: {skill_file}")
        return str(skill_file)

    def update_skill(self, skill_name: str, new_observations: str) -> str:
        """Update an existing skill with new learnings."""
        skill_path = self.skills_dir / skill_name / "SKILL.md"
        if not skill_path.exists():
            return self.create_skill(new_observations, new_observations, skill_name)

        current = skill_path.read_text(encoding="utf-8")
        prompt = f"""
Update the following skill file with new learnings. Keep the format identical.
Only update the content based on new observations -- don't remove existing good advice.
Increment the version number.

CURRENT SKILL:
{current}

NEW OBSERVATIONS:
{new_observations}
"""
        updated = self.llm.generate(prompt, max_tokens=2000)
        skill_path.write_text(updated, encoding="utf-8")
        print(f"[skill_creator] Updated skill: {skill_path}")
        return str(skill_path)
