import difflib
import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from deepresearch.config import Config
from deepresearch.llm_client import LLMClient
from deepresearch.utils import sanitize_dirname
from deepresearch.mermaid_fixer import fix_all_mermaid

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

WRITING STYLE & THE "WHY" (CAUSAL CHAINS)
- Academic but accessible tone — precise terminology, clear explanations.
- Focus heavily on the "WHY" and "HOW". Do not just list risks (the "what"); you MUST explain the exact transmission mechanisms and causal chains (e.g., "Military spending increases -> energy disruption -> persistent inflation -> Federal Reserve cannot cut rates -> banking stress requires direct fiscal bailout").
- Each section MUST open with a strong topic sentence that states the conclusion first, then supports it with interconnected logic.

## STRUCTURE & FORMATTING

ANTI-HALLUCINATION RULES
------------------------

* If the provided context lacks specific data you need (a date, a number, a name), state "The available sources do not specify [detail]" — do NOT invent it.
* Never assert a specific percentage, dollar amount, or statistic unless it appears verbatim in the provided context.
* If multiple sources conflict on a fact, state the disagreement explicitly: "Source A claims X, while Source B reports Y."
* Distinguish between factual claims from sources and your own analytical synthesis.

ANTI-DEDUPLICATION RULES (CRITICAL)
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
        self._emitted_headings: set[str] = set()
        self._open_parents: set[tuple[str, ...]] = set()

    def build_report(
        self,
        topics_json: dict,
        progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> str:
        def emit(event_type: str, data: dict[str, Any] | None = None):
            if progress_callback:
                progress_callback(event_type, data or {})

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
        self._sections_written = 0
        self._topics_processed = 0
        self._total_topics = self._count_topics(topics_json)
        self._emitted_headings.clear()
        self._open_parents.clear()

        logger.info("Starting full report construction...")
        emit("synth_report_start", {
            "total_topics": self._total_topics,
            "message": f"Starting report generation ({self._total_topics} topics)...",
        })
        rolling_summary = self._traverse_topics(topics_json, [], report_file, scratch_pad, rolling_summary, emit)

        if self.accumulator:
            rolling_summary = self._flush_accumulator(report_file, scratch_pad, rolling_summary, emit)

        raw = report_file.read_text(encoding="utf-8") if report_file.exists() else ""
        fixed = fix_all_mermaid(raw)

        if fixed != raw:
            report_file.write_text(fixed, encoding="utf-8")
            logger.info("Fixed malformed Mermaid blocks in report")

        emit("synth_report_complete", {
            "sections_written": self._sections_written,
            "total_topics": self._total_topics,
            "message": f"Report complete — {self._sections_written} sections written.",
        })
        return fixed

    def _count_topics(self, topics_dict: dict) -> int:
        count = 0
        for _topic, subtopics in topics_dict.items():
            count += 1
            if isinstance(subtopics, dict) and subtopics:
                count += self._count_topics(subtopics)
        return count

    def _flush_accumulator(
        self,
        report_file: Path,
        scratch_pad: str,
        rolling_summary: str,
        emit: Callable[[str, dict[str, Any]], None],
    ) -> str:
        if not self.accumulator:
            return rolling_summary

        self._sections_written += 1
        combined_context = ""
        for item in self.accumulator:
            path_str = " > ".join(item['path'])
            combined_context += f"### Topic Path: {path_str}\n{item['context']}\n\n"

        section_title = " > ".join(item['path'][-1] for item in self.accumulator if item.get('path'))
        logger.info("Generating section %s: %s (Tokens: %s)...", self._sections_written, section_title, self.accumulator_tokens)
        emit("synth_report_section", {
            "section_number": self._sections_written,
            "section_title": section_title or "Untitled Section",
            "accumulator_tokens": self.accumulator_tokens,
            "topics_processed": self._topics_processed,
            "total_topics": self._total_topics,
            "message": f"Writing section {self._sections_written}: {section_title or 'Untitled'}...",
        })

        system_prompt = SYSTEM_PROMPT_REPORT_BUILDER

        # ── Anti-duplication prompt: tell LLM which headings are already written ──
        anti_dup_prompt = ""
        if self._emitted_headings:
            emitted_list = "\n".join(f"- {h}" for h in sorted(self._emitted_headings))
            anti_dup_prompt = f"""## CRITICAL ANTI-DUPLICATION RULE
The following headings have ALREADY been written in previous sections:
{emitted_list}

If any topic path shares a parent heading with the list above,
DO NOT output that parent heading again. Output ONLY the subtopic headings that are NEW.
For example, if "Photosynthesis > Light Reactions" is already written,
and you're now writing "Photosynthesis > Calvin Cycle", only output "### Calvin Cycle",
NOT "## Photosynthesis" again.
"""

        prompt = f"""
## Accumulated Topic Paths and Contexts
{combined_context}

{anti_dup_prompt}
## Rolling Summary (what has been written so far)
{rolling_summary}

## Global Scratch Pad Notes
{scratch_pad}
"""

        try:
            section_content = self.llm.generate(
                prompt,
                system=system_prompt,
                max_tokens=self.config.max_tokens,
            )

            # Mechanical safety net: strip any headings already emitted
            section_content = self._deduplicate_section_headings(section_content)

            with open(report_file, "a", encoding="utf-8") as f:
                f.write("\n\n" + section_content)

            # Mark all headings in this flush as emitted
            for item in self.accumulator:
                path = item["path"]
                for i in range(1, len(path) + 1):
                    heading = " > ".join(path[:i])
                    self._emitted_headings.add(heading)

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

    def _deduplicate_section_headings(self, content: str) -> str:
        """Post-process generated content to strip headings already emitted.

        This is a mechanical safety net for emergency flushes where the
        LLM may have ignored the anti-duplication prompt.
        """
        lines = content.split("\n")
        cleaned: list[str] = []
        removed = 0

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                # Extract heading text: "## Photosynthesis" -> "Photosynthesis"
                heading_text = stripped.lstrip("#").strip()
                if not heading_text:
                    cleaned.append(line)
                    continue

                # Check if this exact heading was already emitted
                if heading_text in self._emitted_headings:
                    removed += 1
                    continue

                # Check if any emitted path ends with this heading
                # e.g. "Light Reactions" matches "Photosynthesis > Light Reactions"
                for emitted in self._emitted_headings:
                    if emitted.endswith(" > " + heading_text):
                        removed += 1
                        break
                else:
                    cleaned.append(line)
            else:
                cleaned.append(line)

        if removed:
            logger.info("Post-process removed %s duplicate headings", removed)
        return "\n".join(cleaned)

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

    def _sort_topics_intelligently(
        self,
        topics_dict: dict,
        current_path: list[str],
    ) -> list[tuple[str, Any]]:
        """Ask the LLM to order topics for maximum narrative coherence.

        Only invoked when there are multiple (>1) sibling topics.
        Skipped for leaves or single-child nodes.
        """
        if len(topics_dict) <= 1:
            return list(topics_dict.items())

        # Build lightweight summaries for each topic
        topic_summaries = []
        for topic, subtopics in topics_dict.items():
            path_for_node = current_path + [topic]
            safe_path = [sanitize_dirname(p) or "unknown" for p in path_for_node]
            node_dir = self.indexes_dir.joinpath(*safe_path)

            summary = ""
            if node_dir.exists() and node_dir.is_dir():
                if (node_dir / "overview.md").exists():
                    summary = (node_dir / "overview.md").read_text(encoding="utf-8")[:200]
                elif (node_dir / "information.md").exists():
                    summary = (node_dir / "information.md").read_text(encoding="utf-8")[:200]

            child_count = len(subtopics) if isinstance(subtopics, dict) else 0
            topic_summaries.append({
                "name": topic,
                "summary": summary.strip(),
                "has_children": child_count > 0,
                "child_count": child_count,
            })

        prompt = f"""You are an expert research report architect.

Given the following topics at the current level, determine the OPTIMAL order to present them in a research report for maximum narrative coherence and logical flow.

Rules:
1. Foundational / background topics should come FIRST
2. Topics that other topics depend on should come before their dependents
3. Chronological sequences should be preserved when relevant
4. Broader themes should precede specific details
5. The order should tell a compelling story

Return ONLY a JSON array of topic names in the desired order.
Example: ["Topic A", "Topic B", "Topic C"]

Topics:
{json.dumps(topic_summaries, indent=2)}
"""

        try:
            response = self.llm.json(
                prompt,
                system="You order research topics for maximum coherence. Return only [strictly , dont print anything else except the JSON array] a JSON array of strings.",
                max_tokens=1000,
            )

            ordered_names: list[str] = []

            # ── Response structure repair ──────────────────────────────
            if isinstance(response, list):
                ordered_names = [str(item) for item in response if item is not None]
            elif isinstance(response, dict):
                # Try common wrapper keys (LLMs love wrapping arrays)
                for key in ("order", "topics", "sorted_topics", "result", "data", "items"):
                    if key in response and isinstance(response[key], list):
                        ordered_names = [str(item) for item in response[key] if item is not None]
                        break
                # Fallback: single-key dict where the value is the array
                if not ordered_names and len(response) == 1:
                    sole_value = next(iter(response.values()))
                    if isinstance(sole_value, list):
                        ordered_names = [str(item) for item in sole_value if item is not None]
            elif isinstance(response, str):
                # Sometimes repair_json returns a string that looks like an array
                stripped = response.strip()
                if stripped.startswith("[") and stripped.endswith("]"):
                    try:
                        parsed = json.loads(stripped)
                        if isinstance(parsed, list):
                            ordered_names = [str(item) for item in parsed if item is not None]
                    except json.JSONDecodeError:
                        pass

            if not ordered_names:
                raise ValueError(
                    f"Unexpected response format: {type(response).__name__} = {str(response)[:200]}"
                )

            # ── Content validation & repair ────────────────────────────
            name_set = set(topics_dict.keys())
            ordered: list[tuple[str, Any]] = []
            seen: set[str] = set()
            remaining = set(name_set)

            for name in ordered_names:
                if name in remaining:
                    ordered.append((name, topics_dict[name]))
                    seen.add(name)
                    remaining.discard(name)
                else:
                    # Try similarity-based matching for near-misses
                    similar = self._find_similar_topic(name, remaining)
                    if similar:
                        logger.debug(
                            "Similarity match: LLM returned '%s' → matched to '%s'",
                            name, similar,
                        )
                        ordered.append((similar, topics_dict[similar]))
                        seen.add(similar)
                        remaining.discard(similar)
                    else:
                        logger.debug(
                            "LLM returned unknown topic '%s' at level %s; skipping",
                            name, " > ".join(current_path) or "root",
                        )

            # Append any missing topics at the end (never drop content)
            for name in topics_dict:
                if name not in seen:
                    ordered.append((name, topics_dict[name]))

            # Safety: if we matched very few topics via LLM, fall back to original
            if len(seen) < len(name_set) * 0.5:
                logger.warning(
                    "LLM ordering only matched %s/%s topics at level '%s'; "
                    "falling back to original order.",
                    len(seen), len(name_set),
                    " > ".join(current_path) or "root",
                )
                return list(topics_dict.items())

            logger.info(
                "Intelligently sorted %s topics at level '%s' → order: %s",
                len(topics_dict),
                " > ".join(current_path) or "root",
                [n for n, _ in ordered],
            )
            return ordered

        except Exception as e:
            logger.warning(
                "LLM topic ordering failed at level '%s': %s. Using original order.",
                " > ".join(current_path) or "root",
                e,
            )
            return list(topics_dict.items())

    def _find_similar_topic(
        self,
        candidate: str,
        candidates: set[str],
        threshold: float = 0.6,
    ) -> str | None:
        """Find the most similar topic name using difflib.SequenceMatcher.

        Args:
            candidate: The topic name to match (from LLM response).
            candidates: Set of remaining valid topic names.
            threshold: Minimum similarity ratio (0.0-1.0) to accept a match.

        Returns:
            The best matching topic name, or None if no match exceeds threshold.
        """
        if not candidates:
            return None

        best_match = None
        best_ratio = 0.0

        for topic_name in candidates:
            ratio = difflib.SequenceMatcher(
                None,
                candidate.lower(),
                topic_name.lower(),
            ).ratio()
            if ratio > best_ratio and ratio >= threshold:
                best_ratio = ratio
                best_match = topic_name

        return best_match

    def _traverse_topics(
        self,
        topics_dict: dict,
        current_path: list[str],
        report_file: Path,
        scratch_pad: str,
        rolling_summary: str,
        emit: Callable[[str, dict[str, Any]], None],
    ) -> str:
        sorted_items = self._sort_topics_intelligently(topics_dict, current_path)

        for topic, subtopics in sorted_items:
            path_for_node = current_path + [topic]
            self._topics_processed += 1
            has_children = isinstance(subtopics, dict) and subtopics

            safe_path = [sanitize_dirname(p) or "unknown" for p in path_for_node]
            node_dir = self.indexes_dir.joinpath(*safe_path)

            local_context = ""
            if node_dir.exists() and node_dir.is_dir():
                if (node_dir / "overview.md").exists():
                    local_context = (node_dir / "overview.md").read_text(encoding="utf-8")
                elif (node_dir / "information.md").exists():
                    local_context = (node_dir / "information.md").read_text(encoding="utf-8")

            # Mark as open parent BEFORE adding content or checking flush
            # so we don't split a parent from its children
            if has_children:
                self._open_parents.add(tuple(path_for_node))

            if local_context:
                estimated_tokens = len(local_context) // 4
                self.accumulator.append({
                    "path": path_for_node,
                    "context": local_context
                })
                self.accumulator_tokens += estimated_tokens

            # ── Boundary-aware flush ──────────────────────────────────────
            threshold = getattr(self.config, 'min_accumulator_threshold', 400)
            emergency_threshold = threshold * 5

            if self.accumulator_tokens >= threshold:
                # Only flush if no open parents (all branches complete)
                if not self._open_parents:
                    rolling_summary = self._flush_accumulator(
                        report_file, scratch_pad, rolling_summary, emit,
                    )
                elif self.accumulator_tokens >= emergency_threshold:
                    logger.warning(
                        "Emergency flush mid-parent: %s tokens "
                        "(threshold=%s, emergency=%s)",
                        self.accumulator_tokens, threshold, emergency_threshold,
                    )
                    rolling_summary = self._flush_accumulator(
                        report_file, scratch_pad, rolling_summary, emit,
                    )

            if has_children:
                rolling_summary = self._traverse_topics(
                    subtopics, path_for_node, report_file, scratch_pad,
                    rolling_summary, emit,
                )
                self._open_parents.discard(tuple(path_for_node))

            # Check flush again after children are processed
            if self.accumulator_tokens >= threshold:
                if not self._open_parents:
                    rolling_summary = self._flush_accumulator(
                        report_file, scratch_pad, rolling_summary, emit,
                    )
                elif self.accumulator_tokens >= emergency_threshold:
                    logger.warning(
                        "Emergency flush after children: %s tokens",
                        self.accumulator_tokens,
                    )
                    rolling_summary = self._flush_accumulator(
                        report_file, scratch_pad, rolling_summary, emit,
                    )

        return rolling_summary
