"""Report builder — enhanced with rolling_summary and scratch_pad state injection."""
from __future__ import annotations
import re
from pathlib import Path


class ReportBuilder:
    """Traverses topics_json and constructs the final markdown report section-by-section."""

    def __init__(self, llm, config):
        self.llm = llm
        self.config = config
        self.indexes_dir = Path(config.indexes_dir)

    def build_report(
        self,
        topics_json: dict,
        rolling_summary: str = "",
        scratch_pad: str = "",
    ) -> str:
        """Build full report. rolling_summary and scratch_pad are injected from ResearchState."""
        report_file = Path("report-content.md")
        if report_file.exists():
            report_file.unlink()

        # Use passed-in context (from rolling_summary + scratch_pad) instead of reading files
        initial_summary = rolling_summary or "Report is just starting."
        scratch_ctx = scratch_pad or ""

        print("[report_builder] Starting full report construction...")
        self._traverse_topics(topics_json, [], report_file, scratch_ctx, initial_summary)

        return report_file.read_text(encoding="utf-8") if report_file.exists() else ""

    def _traverse_topics(
        self,
        topics_dict: dict,
        current_path: list[str],
        report_file: Path,
        scratch_pad: str,
        rolling_summary: str,
    ) -> str:
        for topic, subtopics in topics_dict.items():
            path_for_node = current_path + [topic]
            safe_path = [_sanitize(p) for p in path_for_node]
            node_dir = self.indexes_dir.joinpath(*safe_path)

            # Read overview or information for this node
            local_context = ""
            if node_dir.exists():
                for fname in ["overview.md", "information.md"]:
                    f = node_dir / fname
                    if f.exists():
                        local_context = f.read_text(encoding="utf-8")
                        break

            if local_context:
                print(f"[report_builder] Writing: {' > '.join(path_for_node)}")
                system_prompt = """You are a master research report writer.
Given the section's topic path, source context, scratch pad notes, and rolling summary of the report so far:
- Write ONLY the Markdown content for this specific section
- Ensure smooth transitions from the rolling summary
- Include evidence and citations from the context
- Keep tone objective and professional
- Do NOT rewrite earlier sections"""

                prompt = f"""## Current Topic Path
{' > '.join(path_for_node)}

## Rolling Summary (what has been written so far)
{rolling_summary[-1000:]}

## Global Scratch Pad Notes
{scratch_pad[:1500]}

## Local Context (Overview/Information for this topic)
{local_context[:8000]}
"""
                try:
                    section_content = self.llm.generate(
                        prompt,
                        system=system_prompt,
                        use_claude=True,
                        max_tokens=self.config.max_tokens,
                    )

                    with open(report_file, "a", encoding="utf-8") as f:
                        heading_level = min(len(path_for_node) + 1, 6)
                        f.write(f"\n\n{'#' * heading_level} {topic}\n\n")
                        f.write(section_content)

                    # Update rolling summary
                    summary_prompt = f"""Update the rolling summary with the new section.
Current Summary:
{rolling_summary}

New Section Added:
{section_content[:2000]}...

Write a concise updated rolling summary that captures the narrative flow so far."""
                    rolling_summary = self.llm.generate(
                        summary_prompt,
                        system="You are a concise summarization assistant.",
                        max_tokens=1000,
                    )

                except Exception as e:
                    print(f"[report_builder] Failed on {' > '.join(path_for_node)}: {e}")

            if isinstance(subtopics, dict) and subtopics:
                rolling_summary = self._traverse_topics(
                    subtopics, path_for_node, report_file, scratch_pad, rolling_summary
                )

        return rolling_summary


def _sanitize(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_\-]", "_", name).strip("_")
