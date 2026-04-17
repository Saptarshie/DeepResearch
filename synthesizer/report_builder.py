import re
from pathlib import Path
from deepresearch.llm_client import LLMClient
from deepresearch.config import Config

class ReportBuilder:
    def __init__(self, llm: LLMClient, config: Config):
        self.llm = llm
        self.config = config
        self.indexes_dir = Path(config.indexes_dir)

    def _sanitize_dirname(self, name: str) -> str:
        return re.sub(r'[^a-zA-Z0-9_\-]', '_', name).strip('_')

    def build_report(self, topics_json: dict) -> str:
        report_file = Path("report-content.md")
        if report_file.exists():
            report_file.unlink()
            
        scratch_pad = ""
        if Path("scratch_pad.md").exists():
            scratch_pad = Path("scratch_pad.md").read_text(encoding="utf-8")
            
        rolling_summary = "This report is just starting."
        
        print("[report_builder] Starting full report construction...")
        self._traverse_topics(topics_json, [], report_file, scratch_pad, rolling_summary)
        
        return report_file.read_text(encoding="utf-8") if report_file.exists() else ""

    def _traverse_topics(self, topics_dict: dict, current_path: list[str], report_file: Path, scratch_pad: str, rolling_summary: str) -> str:
        for topic, subtopics in topics_dict.items():
            path_for_node = current_path + [topic]
            
            safe_path = [self._sanitize_dirname(p) for p in path_for_node]
            node_dir = self.indexes_dir.joinpath(*safe_path)
            
            local_context = ""
            if node_dir.exists() and node_dir.is_dir():
                if (node_dir / "overview.md").exists():
                    local_context = (node_dir / "overview.md").read_text(encoding="utf-8")
                elif (node_dir / "information.md").exists():
                    local_context = (node_dir / "information.md").read_text(encoding="utf-8")
                    
            if local_context:
                print(f"[report_builder] Generating section for: {' > '.join(path_for_node)}")
                
                system_prompt = """You are a master research report writer. 
Given the current section's topic path, contextual information, global scratch pad hints, and the rolling summary of the report so far, your task is to write ONLY the Markdown content for this specific section.
Follow these guidelines:
- Ensure smooth transitions based on the rolling summary.
- Incorporate evidence from the context (using citations if present).
- DO NOT rewrite the entire report. Only write the new component.
- Keep the tone objective and professional."""

                prompt = f"""
## Current Topic Path
{' > '.join(path_for_node)}

## Rolling Summary (what has been written so far)
{rolling_summary}

## Global Scratch Pad Notes
{scratch_pad}

## Local Context (Overview/Information for this topic)
{local_context}
"""
                try:
                    section_content = self.llm.generate(
                        prompt,
                        system=system_prompt,
                        use_claude=True,
                        max_tokens=self.config.max_tokens
                    )
                    
                    with open(report_file, "a", encoding="utf-8") as f:
                        # Only add the topic header if it's the first time
                        heading_level = min(len(path_for_node) + 1, 6)
                        f.write(f"\n\n{'#' * heading_level} {topic}\n\n")
                        f.write(section_content)
                        
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
                    print(f"[report_builder] Failed on {' > '.join(path_for_node)}: {e}")
                    
            if isinstance(subtopics, dict) and subtopics:
                rolling_summary = self._traverse_topics(subtopics, path_for_node, report_file, scratch_pad, rolling_summary)
                
        return rolling_summary
