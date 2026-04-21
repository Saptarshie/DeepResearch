"""Skill loader — dynamically load SKILLS/*/SKILL.md files."""
from __future__ import annotations
from pathlib import Path
from omega_researcher.schemas import Skill
from omega_researcher.config import Config


class SkillLoader:
    """Load and select skills from the SKILLS/ directory."""

    def __init__(self, config: Config):
        self.skills_dir = Path(config.skills_dir)
        self._cache: dict[str, Skill] = {}

    def load_all(self) -> list[Skill]:
        """Load all SKILLS/*/SKILL.md files."""
        if not self.skills_dir.exists():
            return []

        skills = []
        for skill_file in self.skills_dir.rglob("SKILL.md"):
            try:
                skill = self._parse_skill_file(skill_file)
                self._cache[skill.name] = skill
                skills.append(skill)
            except Exception as e:
                print(f"[skill_loader] Failed to load {skill_file}: {e}")
        return skills

    def load_for_task(self, task_description: str, llm) -> list[Skill]:
        """
        Use LLM to select which skills are relevant for this task.
        Returns a subset of loaded skills.
        """
        all_skills = self.load_all()
        if not all_skills:
            return []

        skills_summary = "\n".join(
            f"- {s.name}: {s.description[:200]}" for s in all_skills
        )
        prompt = f"""
Task: {task_description}

Available skills:
{skills_summary}

Which skills are relevant for this task? Return a JSON list of skill names.
Example: ["data_analysis", "web_scraping"]
"""
        try:
            selected = llm.json(prompt, system="Return JSON list of skill names only.")
            if isinstance(selected, list):
                return [self._cache[n] for n in selected if n in self._cache]
            return []
        except Exception:
            return []

    def get(self, name: str) -> Skill | None:
        """Get a cached skill by name."""
        if not self._cache:
            self.load_all()
        return self._cache.get(name)

    def list_names(self) -> list[str]:
        """Return all skill names."""
        if not self._cache:
            self.load_all()
        return list(self._cache.keys())

    def _parse_skill_file(self, path: Path) -> Skill:
        """Parse a SKILL.md file with YAML frontmatter."""
        content = path.read_text(encoding="utf-8")

        meta = {}
        parts = content.split("---", 2)
        if len(parts) >= 3:
            try:
                import yaml
                meta = yaml.safe_load(parts[1]) or {}
            except Exception:
                meta = {}

        return Skill(
            name=meta.get("name", path.parent.name),
            description=str(meta.get("description", "")),
            path=str(path),
            content=content,
            tags=meta.get("tags", []),
            version=str(meta.get("version", "1.0")),
        )
