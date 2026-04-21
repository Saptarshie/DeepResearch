"""Experience logger — append-only log of research outcomes."""
from __future__ import annotations
import json
from pathlib import Path
from datetime import datetime
from omega_researcher.schemas import Experience


class ExperienceLogger:
    """
    Append-only log of research outcomes.
    Written by MetaAgent in a separate LLM context.
    Format: JSONL (one Experience per line) + human-readable experiences.md
    """

    def __init__(self, config):
        self.path = Path(config.experiences_path)
        self.jsonl_path = self.path.with_suffix(".jsonl")

    def log(self, exp: Experience) -> None:
        """Append experience to both JSONL and markdown."""
        # JSONL for machine reading
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(exp.__dict__) + "\n")

        # Markdown for human reading + LLM reading
        md = f"""
---
## Experience: {exp.timestamp}
**Query:** {exp.query}
**Outcome:** {exp.outcome} (coverage: {exp.coverage_achieved:.0%})
**Duration:** {exp.duration_seconds:.1f}s | **Docs:** {exp.total_docs} | **Subagents:** {exp.subagents_spawned}

**Skills used:** {", ".join(exp.skills_used) or "none"}
**Tools used:** {", ".join(exp.tools_used)}

### What worked
{exp.what_worked}

### What failed
{exp.what_failed}

### Suggestions for next time
{exp.suggestions}
"""
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(md)

    def read_all(self) -> list[Experience]:
        """Read all experiences from JSONL."""
        if not self.jsonl_path.exists():
            return []
        results = []
        with open(self.jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    results.append(Experience(**json.loads(line)))
                except Exception:
                    pass
        return results

    def read_failures(self) -> list[Experience]:
        """Return only failed/partial experiences."""
        return [e for e in self.read_all() if e.outcome in ("failure", "partial")]

    def read_for_query_type(self, query_keywords: list[str]) -> list[Experience]:
        """Find past experiences matching keywords."""
        all_exp = self.read_all()
        return [
            e for e in all_exp
            if any(kw.lower() in e.query.lower() for kw in query_keywords)
        ]

    def count(self) -> int:
        """Return total number of experiences logged."""
        if not self.jsonl_path.exists():
            return 0
        with open(self.jsonl_path, "r", encoding="utf-8") as f:
            return sum(1 for line in f if line.strip())

    def __repr__(self) -> str:
        return f"ExperienceLogger(path={self.path}, count={self.count()})"
