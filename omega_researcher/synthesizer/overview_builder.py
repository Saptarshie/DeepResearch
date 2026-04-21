"""Overview builder — post-order DFS over INDEXES/ tree."""
from pathlib import Path


class OverviewBuilder:
    """Synthesize overview.md files bottom-up via post-order DFS."""

    def __init__(self, llm, config):
        self.llm = llm
        self.config = config

    def build_overview(self, root_path: Path | str) -> str:
        root_path = Path(root_path)
        if not root_path.exists() or not root_path.is_dir():
            return ""

        subdirs = [d for d in root_path.iterdir() if d.is_dir()]
        info_file = root_path / "information.md"
        local_content = ""
        if info_file.exists():
            local_content = info_file.read_text(encoding="utf-8")

        if not subdirs:
            return local_content

        # Recursive: build children first (post-order)
        context = ""
        for d in subdirs:
            child_summary = self.build_overview(d)
            if child_summary:
                context += f"\n\n### Subtopic: {d.name}\n{child_summary}"

        if local_content:
            context += f"\n\n### Local Information\n{local_content}"

        if not context.strip():
            return ""

        print(f"[overview_builder] Synthesizing: {root_path.name}")
        system_prompt = """You are an advanced synthesis engine.
Summarize and integrate the provided subtopic information into a coherent, comprehensive overview.
Do not lose key facts or citations. Use clean Markdown. Be objective and factual."""

        try:
            overview_content = self.llm.generate(
                f"Synthesize the following research context:\n\n{context[:12000]}",
                system=system_prompt,
                use_claude=True,
                max_tokens=self.config.max_tokens,
            )
        except Exception as e:
            print(f"[overview_builder] Failed for {root_path}: {e}")
            overview_content = context

        (root_path / "overview.md").write_text(overview_content, encoding="utf-8")
        return overview_content
