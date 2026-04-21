"""Thread-safe scratch pad — shared mutable working memory for all agents."""
from __future__ import annotations
import re
import threading
from pathlib import Path


class ScratchPad:
    """
    Thread-safe scratch pad for shared ephemeral notes.
    All agents (including subagents) write here.
    
    Internal structure:
        ## Global Notes
        ...
        ## SubAgent: {task_id}
        ...
        ## Contradictions
        ...
        ## Open Questions
        ...
    """
    _lock = threading.Lock()

    def __init__(self, path: str = "scratch_pad.md"):
        self.path = Path(path)
        self._sections: dict[str, str] = {
            "Global Notes": "",
            "Contradictions": "",
            "Open Questions": "",
        }
        if self.path.exists():
            self._load()

    # ── Public API ────────────────────────────────────────────────────────

    def write(self, section: str, content: str) -> None:
        """Overwrite a section entirely."""
        with self._lock:
            self._sections[section] = content
            self._flush()

    def append(self, section: str, content: str) -> None:
        """Append text to a section."""
        with self._lock:
            self._sections.setdefault(section, "")
            self._sections[section] += f"\n{content}"
            self._flush()

    def read(self, section: str | None = None) -> str:
        """Read one section, or all sections concatenated."""
        if section:
            return self._sections.get(section, "")
        return "\n\n".join(
            f"## {k}\n{v}" for k, v in self._sections.items() if v.strip()
        )

    def clear(self) -> None:
        """Reset scratch pad to empty."""
        with self._lock:
            self._sections = {
                "Global Notes": "",
                "Contradictions": "",
                "Open Questions": "",
            }
            self._flush()

    # ── Internal ──────────────────────────────────────────────────────────

    def _flush(self) -> None:
        text = "# Scratch Pad\n\n" + self.read()
        self.path.write_text(text, encoding="utf-8")

    def _load(self) -> None:
        text = self.path.read_text(encoding="utf-8")
        matches = re.split(r"^## (.+)$", text, flags=re.MULTILINE)
        # matches: ['prefix', 'SectionName', 'content', 'SectionName2', 'content2', ...]
        for i in range(1, len(matches) - 1, 2):
            self._sections[matches[i].strip()] = matches[i + 1].strip()

    def __repr__(self) -> str:
        keys = list(self._sections.keys())
        return f"ScratchPad(sections={keys}, path={self.path})"
