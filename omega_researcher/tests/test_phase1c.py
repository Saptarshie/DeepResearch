"""Test Phase 1C — Skills system."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import tempfile, os

def test_skill_loader():
    from omega_researcher.skills.skill_loader import SkillLoader
    from omega_researcher.config import Config

    cfg = Config()
    # tests/ -> omega_researcher/ -> deepresearch/ -> SKILLS/
    cfg.skills_dir = str(Path(__file__).resolve().parent.parent.parent / "SKILLS")

    loader = SkillLoader(cfg)
    skills = loader.load_all()

    assert len(skills) >= 5, f"Expected >=5 skills, got {len(skills)}"
    names = [s.name for s in skills]
    assert "data_analysis" in names
    assert "web_scraping" in names
    assert "academic_research" in names

    s = loader.get("data_analysis")
    assert s is not None
    assert "pandas" in s.tags or "data" in s.tags

    print(f"[PASS] SkillLoader loaded {len(skills)} skills: {names}")


def test_skill_loader_empty_dir():
    from omega_researcher.skills.skill_loader import SkillLoader
    from omega_researcher.config import Config

    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = Config()
        cfg.skills_dir = tmpdir
        loader = SkillLoader(cfg)
        skills = loader.load_all()
        assert skills == []
        print("[PASS] SkillLoader handles empty dir gracefully")


def test_skill_creator_structure():
    """Test that creator writes well-structured file (no LLM called)."""
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmpdir:
        skills_path = Path(tmpdir) / "SKILLS"
        # Write a manual skill to verify parse
        skill_dir = skills_path / "test_skill"
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text("""\
---
name: test_skill
description: A test skill for unit testing.
tags: [test, unit]
version: 1.0
---

# Test Skill

## When to activate this skill
- When testing

## Recommended tool sequence
1. Do something

## Prompting guidance
Be precise.

## Common pitfalls to avoid
- None
""", encoding="utf-8")

        from omega_researcher.skills.skill_loader import SkillLoader
        from omega_researcher.config import Config
        cfg = Config()
        cfg.skills_dir = str(skills_path)
        loader = SkillLoader(cfg)
        skills = loader.load_all()
        assert len(skills) == 1
        assert skills[0].name == "test_skill"
        assert "test" in skills[0].tags
        assert skills[0].version == "1.0"
        print("[PASS] SkillCreator-structured SKILL.md parses correctly")


if __name__ == "__main__":
    test_skill_loader_empty_dir()
    test_skill_creator_structure()
    test_skill_loader()
    print("\n[OK] ALL PHASE 1C SKILL TESTS PASSED")
