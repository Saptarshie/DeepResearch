import logging
from pathlib import Path

from deepresearch.config import Config
from deepresearch.llm_client import LLMClient
from deepresearch.utils import sanitize_dirname

logger = logging.getLogger(__name__)

class ReportBuilder:
    def __init__(self, llm: LLMClient, config: Config):
        self.llm = llm
        self.config = config
        self.indexes_dir = Path(config.indexes_dir)

    def build_report(self, topics_json: dict) -> str:
        report_file = Path(self.config.workspace_dir) / "report-content.md"
        report_file.parent.mkdir(parents=True, exist_ok=True)
        if report_file.exists():
            report_file.unlink()

        scratch_pad_path = Path(self.config.workspace_dir) / "scratch_pad.md"
        scratch_pad = ""
        if scratch_pad_path.exists():
            scratch_pad = scratch_pad_path.read_text(encoding="utf-8")

        rolling_summary = "This report is just starting."

        self.accumulator = []
        self.accumulator_tokens = 0

        logger.info("Starting full report construction...")
        rolling_summary = self._traverse_topics(topics_json, [], report_file, scratch_pad, rolling_summary)

        if self.accumulator:
            rolling_summary = self._flush_accumulator(report_file, scratch_pad, rolling_summary)

        return report_file.read_text(encoding="utf-8") if report_file.exists() else ""

    def _flush_accumulator(self, report_file: Path, scratch_pad: str, rolling_summary: str) -> str:
        if not self.accumulator:
            return rolling_summary

        combined_context = ""
        for item in self.accumulator:
            path_str = " > ".join(item['path'])
            combined_context += f"### Topic Path: {path_str}\n{item['context']}\n\n"

        logger.info("Generating section for accumulated topics (Tokens: %s)...", self.accumulator_tokens)

        system_prompt = """You are a master research report writer. 
Given the accumulated topic paths, contextual information, global scratch pad hints, and the rolling summary of the report so far, your task is to write ONLY the Markdown content for these specific sections.
Follow these guidelines:
- Ensure smooth transitions based on the rolling summary.
- Incorporate evidence from the context (using citations if present).
- DO NOT rewrite the entire report. Only write the new components.
- Keep the tone objective and professional.
- Appropriately use markdown headings based on the topic structure."""

        prompt = f"""
## Accumulated Topic Paths and Contexts
{combined_context}

## Rolling Summary (what has been written so far)
{rolling_summary}

## Global Scratch Pad Notes
{scratch_pad}
"""
        try:
            section_content = self.llm.generate(
                prompt,
                system=system_prompt,
                provider="anthropic",
                max_tokens=self.config.max_tokens,
            )

            with open(report_file, "a", encoding="utf-8") as f:
                f.write("\n\n" + section_content)

            self.accumulator = []
            self.accumulator_tokens = 0
        except Exception as e:
            logger.warning("Failed on accumulated sections: %s", e)
            return rolling_summary

        try:
            summary_prompt = f"""Update the rolling summary with the new section.
Current Summary:
{rolling_summary}

New Section Added:
{section_content[:2000]}...

Write a concise updated rolling summary that captures the flowing narrative so far."""
            rolling_summary = self.llm.generate(
                summary_prompt,
                system="You are a summarization assistant.",
                max_tokens=1000
            )
        except Exception as e:
            logger.warning("Failed to update rolling summary: %s", e)

        return rolling_summary

    def _traverse_topics(self, topics_dict: dict, current_path: list[str], report_file: Path, scratch_pad: str, rolling_summary: str) -> str:
        for topic, subtopics in topics_dict.items():
            path_for_node = current_path + [topic]

            safe_path = [sanitize_dirname(p) or "unknown" for p in path_for_node]
            node_dir = self.indexes_dir.joinpath(*safe_path)

            local_context = ""
            if node_dir.exists() and node_dir.is_dir():
                if (node_dir / "overview.md").exists():
                    local_context = (node_dir / "overview.md").read_text(encoding="utf-8")
                elif (node_dir / "information.md").exists():
                    local_context = (node_dir / "information.md").read_text(encoding="utf-8")

            if local_context:
                estimated_tokens = len(local_context) // 4
                self.accumulator.append({
                    "path": path_for_node,
                    "context": local_context
                })
                self.accumulator_tokens += estimated_tokens

                threshold = getattr(self.config, 'min_accumulator_threshold', 400)
                if self.accumulator_tokens >= threshold:
                    rolling_summary = self._flush_accumulator(report_file, scratch_pad, rolling_summary)

            if isinstance(subtopics, dict) and subtopics:
                rolling_summary = self._traverse_topics(subtopics, path_for_node, report_file, scratch_pad, rolling_summary)

        return rolling_summary
