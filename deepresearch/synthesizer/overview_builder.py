import logging
from pathlib import Path

from deepresearch.config import Config
from deepresearch.llm_client import LLMClient

logger = logging.getLogger(__name__)

class OverviewBuilder:
    def __init__(self, llm: LLMClient, config: Config):
        self.llm = llm
        self.config = config

    def build_overview(self, root_path: Path | str, is_root: bool = True) -> str:
        root_path = Path(root_path)
        if not root_path.exists() or not root_path.is_dir():
            return ""

        # Find subdirectories
        subdirs = [d for d in root_path.iterdir() if d.is_dir()]

        info_file = root_path / "information.md"
        local_content = ""
        if info_file.exists():
            local_content = info_file.read_text(encoding="utf-8")

        if not subdirs:
            # It's a leaf node. We don't necessarily generate an overview.md for leaves if information.md is sufficient,
            # but to be uniform, we can just return it. The plan says "return information.md if its a leaf".
            return local_content

        # Recursive step
        context = ""
        for d in subdirs:
            child_summary = self.build_overview(d, is_root=False)
            if child_summary:
                context += f"\n\n### Subtopic: {d.name}\n{child_summary}"

        if local_content:
            context += f"\n\n### Local Information\n{local_content}"

        if not context.strip():
            return ""

        # Skip LLM for intermediate nodes — deterministic concatenation is sufficient
        if not is_root:
            return context

        # Call LLM to synthesize overall context into an overview (only at root)
        logger.info("Synthesizing overview for %s", root_path)
        system_prompt = """You are an advanced synthesis engine.
Your task is to summarize and integrate the provided contextual information from subtopics and local information into a coherent, comprehensive overview for this directory level.
Do not lose important details, facts, or citations. Keep the formatting as clean Markdown.
Be objective and factual."""

        prompt = f"Please synthesize the following context:\n\n{context}"

        try:
            overview_content = self.llm.generate(
                prompt,
                system=system_prompt,
                max_tokens=self.config.max_tokens,
            )
        except Exception as e:
            logger.warning("Failed to generate overview for %s: %s", root_path, e)
            # Fallback to just concatenating
            overview_content = context

        overview_file = root_path / "overview.md"
        overview_file.write_text(overview_content, encoding="utf-8")

        return overview_content
