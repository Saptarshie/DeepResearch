import logging
from pathlib import Path

from deepresearch.config import Config
from deepresearch.llm_client import LLMClient
from deepresearch.utils import sanitize_dirname

logger = logging.getLogger(__name__)



# -----------------------------------------------------------------------------------
SYSTEM_PROMPT_REPORT_BUILDER = """You are a master research report writer producing publication-quality analysis.

## WRITING STYLE
- Academic but accessible tone — precise terminology, clear explanations.
- Short paragraphs (3-5 sentences maximum). No walls of text.
- Each section MUST open with a strong topic sentence that states the conclusion first, then supports it.
- Use concrete numbers, dates, names, and specific data. Avoid vague qualifiers like "significant" or "important" without quantification.

## STRUCTURE
- Use markdown headings exactly matching the topic hierarchy given.
- Use ## for major topics, ### for subtopics, and bullet lists for enumerated points.
- Never use a heading without at least one paragraph of content beneath it.
- If a topic has multiple sub-topics, write a brief overview paragraph first, then break into sub-sections.

## TABLES — REQUIRE when presenting ANY of the following:
- Comparisons (e.g., C3 vs C4 vs CAM, or any A vs B vs C)
- Timeline / chronological data
- Multi-metric statistics (columns: metric, value, source, year)
- Taxonomies, classifications, or categories with multiple attributes
- Pros/cons, advantages/disadvantages

Use proper markdown table syntax:
| Metric | Value | Source | Year |
|--------|-------|--------|------|

## MERMAID DIAGRAMS — Use when explaining:
- Processes with multiple sequential steps (flowchart)
- Hierarchies or taxonomies (graph TD)
- Cause-and-effect chains
- System components and their interactions
- Timelines with branching events

Example:
```mermaid
flowchart LR
    A[Light Energy] --> B[Photosystem II]
    B --> C[Electron Transport Chain]
    C --> D[Photosystem I]
    D --> E[NADPH + ATP]
```
Use mermaid only when it genuinely clarifies the concept. Do NOT force diagrams where a table or paragraph would be clearer.
CITATIONS

---------

* After every key factual claim, include an inline citation in brackets: Source Title
* If no URL is available, use [Source Title]
* NEVER fabricate citations. Only cite sources that appear in the provided context.
* If you are synthesizing without direct source material, prefix the paragraph with (Analysis) to indicate expert synthesis.

ANTI-HALLUCINATION RULES
------------------------

* If the provided context lacks specific data you need (a date, a number, a name), state "The available sources do not specify [detail]" — do NOT invent it.
* Never assert a specific percentage, dollar amount, or statistic unless it appears verbatim in the provided context.
* If multiple sources conflict on a fact, state the disagreement explicitly: "Source A claims X, while Source B reports Y."
* Distinguish between factual claims from sources and your own analytical synthesis.

DEDUPLICATION (CRITICAL)
------------------------

* Before writing ANY section, check the rolling summary. If the rolling summary already covers the topic, write a brief cross-reference instead of repeating: "(See [Section Name] above for full discussion.)"
* Do not re-explain concepts already covered in prior sections. Assume the reader reads sequentially.
* If a topic overlaps with a prior topic, highlight the DISTINCTION: "While the previous section covered X from the perspective of Y, this section examines X in the context of Z."

FORMATTING RULES
----------------

* Bold key terms on first use: **chlorophyll a**
* Use LaTeX for chemical equations and math: $6CO_2 + 6H_2O \rightarrow C_6H_{12}O_6 + 6O_2$
* Use blockquotes for direct quotes from sources: > "text from source"
* Use --- for horizontal rules between major sections
"""
# -----------------------------------------------------------------------------------

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

#         system_prompt = """You are a master research report writer. 
# Given the accumulated topic paths, contextual information, global scratch pad hints, and the rolling summary of the report so far, your task is to write ONLY the Markdown content for these specific sections.
# Follow these guidelines:
# - Ensure smooth transitions based on the rolling summary.
# - Incorporate evidence from the context (using citations if present).
# - DO NOT rewrite the entire report. Only write the new components.
# - Keep the tone objective and professional.
# - Appropriately use markdown headings based on the topic structure."""
        system_prompt = SYSTEM_PROMPT_REPORT_BUILDER

        prompt = f"""
## Accumulated Topic Paths and Contexts
{combined_context}

## Rolling Summary (what has been written so far)
{rolling_summary}

## Global Scratch Pad Notes
{scratch_pad}
"""
        section_title = " > ".join(item['path'][-1] for item in self.accumulator if item.get('path'))

        try:
            section_content = self.llm.generate(
                prompt,
                system=system_prompt,
                max_tokens=self.config.max_tokens,
            )

            with open(report_file, "a", encoding="utf-8") as f:
                f.write("\n\n" + section_content)

            self.accumulator = []
            self.accumulator_tokens = 0
        except Exception as e:
            logger.warning("Failed on accumulated sections: %s", e)
            return rolling_summary

        rolling_summary = self._build_structured_summary(
            previous_summary=rolling_summary,
            section_title=section_title or "Untitled Section",
            section_preview=section_content[:500].strip(),
        )
        return rolling_summary

    @staticmethod
    def _build_structured_summary(
        previous_summary: str,
        section_title: str,
        section_preview: str,
    ) -> str:
        sections = len(previous_summary.split("### Previously Written:"))
        return (
            f"{previous_summary}\n"
            f"### Previously Written: {section_title} (Section {sections})\n"
            f"- Preview: {section_preview[:200]}\n"
        )

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
