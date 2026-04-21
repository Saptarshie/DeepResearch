"""IndexManager — live index access API wrapping the synthesizer Indexer."""
from __future__ import annotations
import json
import re
from pathlib import Path
from omega_researcher.config import Config
from omega_researcher.schemas import IngestedDocument


class IndexManager:
    """
    Wraps the indexer with a live-access API so the Actor can:
    - Index documents one-at-a-time (INDEX-AS-YOU-GO)
    - Query what's been indexed so far
    - Read specific topic files
    """

    SYSTEM_PROMPT_TEMPLATE = """You are an advanced hierarchical information indexer.
You are given:
- The user's query
- A document's content
- The current topics hierarchy (JSON where keys are topics, values are subtopic dicts)
- The current scratch pad

Your job is to:
1. Update the topics hierarchy with any NEW relevant topics from this document. Max depth: {max_depth}. Keep keys short and descriptive.
2. Extract specific information blocks from the document to place in the appropriate topic/subtopic paths.
   - A path is a list of topic names corresponding to the JSON hierarchy. (e.g. ["AI", "Neural_Networks"])
   - IMPORTANT: Only output information blocks for NEW or significantly expanded content.
3. Update the global scratch pad with important insights or global context.

Respond ONLY in this JSON format:
{{
  "updated_topics_hierarchy": {{ "Topic 1": {{"Subtopic 1": {{}}}}, "Topic 2": {{}} }},
  "extracted_information": [
     {{
       "path": ["Topic 1", "Subtopic 1"],
       "content": "Detailed text from document relevant to this path."
     }}
  ],
  "updated_scratch_pad": "The new scratch pad content."
}}"""

    def __init__(self, config: Config):
        self.indexes_dir = Path(config.indexes_dir)
        self.indexes_dir.mkdir(parents=True, exist_ok=True)
        self.max_depth = config.max_indexer_depth
        self._topics_json: dict = {}
        self._topics_path = Path("topics.json")

        # Load existing topics if present
        if self._topics_path.exists():
            try:
                self._topics_json = json.loads(self._topics_path.read_text(encoding="utf-8"))
            except Exception:
                self._topics_json = {}

    # ── INDEX-AS-YOU-GO ───────────────────────────────────────────────────────

    def index_document(
        self,
        doc: IngestedDocument,
        query: str,
        llm,
        scratch_pad_text: str = "",
    ) -> dict:
        """
        Index a single IngestedDocument immediately after processing.
        Updates self._topics_json in memory AND writes to INDEXES/.
        Returns new topics_json so actor can see what was just learned.
        """
        system = self.SYSTEM_PROMPT_TEMPLATE.format(max_depth=self.max_depth)

        prompt = f"""## User Query
{query}

## Document Info
Title: {doc.title}
Source: {doc.source_path}
Type: {doc.source_type.value}

## Document Content
{doc.text[:10000]}

## Current Topics Hierarchy
{json.dumps(self._topics_json, indent=2)}

## Current Scratch Pad
{scratch_pad_text[:2000]}
"""
        try:
            response = llm.json(prompt, system=system, use_claude=True, max_tokens=8000)

            if "updated_topics_hierarchy" in response:
                self._topics_json = response["updated_topics_hierarchy"]

            scratch_pad_update = response.get("updated_scratch_pad", "")

            for item in response.get("extracted_information", []):
                path = item.get("path", [])
                content = item.get("content", "")
                if not path or not content:
                    continue

                path = path[: self.max_depth]
                safe_path = [_sanitize_dirname(p) or "unknown" for p in path]

                target_dir = self.indexes_dir.joinpath(*safe_path)
                target_dir.mkdir(parents=True, exist_ok=True)

                info_file = target_dir / "information.md"
                with open(info_file, "a", encoding="utf-8") as f:
                    f.write(f"\n### Source: [{doc.title}]({doc.source_path})\n\n{content}\n")

            # Persist updated topics
            self._topics_path.write_text(
                json.dumps(self._topics_json, indent=2), encoding="utf-8"
            )

            return {
                "topics_json": self._topics_json,
                "scratch_pad_update": scratch_pad_update,
            }

        except Exception as e:
            print(f"[index_manager] Error indexing doc '{doc.title}': {e}")
            return {"topics_json": self._topics_json, "scratch_pad_update": ""}

    # ── READ API ──────────────────────────────────────────────────────────────

    def get_topics(self) -> dict:
        """Current in-memory topics hierarchy."""
        return self._topics_json

    def list_topics(self) -> list[str]:
        """Return all leaf topic paths as 'Topic/Subtopic' strings."""
        results = []
        for p in self.indexes_dir.rglob("information.md"):
            rel = p.parent.relative_to(self.indexes_dir)
            results.append(str(rel).replace("\\", "/"))
        return sorted(results)

    def read_index_file(self, path_parts: list[str]) -> str:
        """Read a specific INDEXES/<path>/information.md or overview.md."""
        target = self.indexes_dir.joinpath(*path_parts)
        for fname in ["overview.md", "information.md"]:
            f = target / fname
            if f.exists():
                return f.read_text(encoding="utf-8")
        return ""

    def get_root_overview(self) -> str:
        """Return root INDEXES/overview.md if it exists."""
        f = self.indexes_dir / "overview.md"
        return f.read_text(encoding="utf-8") if f.exists() else ""


def _sanitize_dirname(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", name).strip("_")
