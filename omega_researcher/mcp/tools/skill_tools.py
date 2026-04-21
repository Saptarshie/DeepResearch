"""Skill tools — list/load/create skills via MCP."""
from __future__ import annotations
from omega_researcher.config import Config
from omega_researcher.skills.skill_loader import SkillLoader
from omega_researcher.skills.skill_creator import SkillCreator


class SkillTools:
    def __init__(self, config: Config, llm, skill_loader: SkillLoader):
        self.config = config
        self.llm = llm
        self.loader = skill_loader
        self._creator = None

    def _get_creator(self):
        if self._creator is None:
            self._creator = SkillCreator(self.config, self.llm)
        return self._creator

    def list_all(self) -> str:
        """List all available skills."""
        skills = self.loader.load_all()
        if not skills:
            return "No skills loaded yet."
        lines = ["## Available Skills\n"]
        for s in skills:
            lines.append(f"### {s.name} (v{s.version})\n{s.description[:200]}\n**Tags:** {', '.join(s.tags)}\n")
        return "\n".join(lines)

    def load(self, skill_name: str) -> str:
        """Load and return full SKILL.md content."""
        skill = self.loader.get(skill_name)
        if not skill:
            return f"[skill_tools] Skill '{skill_name}' not found."
        return skill.content

    def create(self, task_description: str, what_worked: str, name: str = "") -> str:
        """Create a new skill and return the file path."""
        creator = self._get_creator()
        path = creator.create_skill(task_description, what_worked, name or None)
        # Reload cache
        self.loader.load_all()
        return f"Skill created at: {path}"
