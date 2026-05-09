import json
import logging
import shutil
from pathlib import Path

from deepresearch.config import Config
from deepresearch.llm_client import LLMClient
from deepresearch.utils import sanitize_dirname

logger = logging.getLogger(__name__)

class Indexer:
    def __init__(self, llm: LLMClient, config: Config):
        self.llm = llm
        self.config = config
        self.indexes_dir = Path(config.indexes_dir)
        self.max_depth = config.max_indexer_depth

    def _build_prompt(
        self, query: str, docs: list[dict], topics_json: dict, scratch_pad: str
    ) -> str:
        docs_section = ""
        for idx, doc in enumerate(docs, 1):
            title = doc.get("title", "Untitled")
            text = doc.get("text", "")[:10000]
            url = doc.get("url", "")
            docs_section += f"""
### Document {idx}
Title: {title}
URL: {url}
Content:
{text}

"""

        return f"""
## User Query
{query}

## Documents
{docs_section}
## Current Topics Hierarchy
{json.dumps(topics_json, indent=2)}

## Current Scratch Pad
{scratch_pad}
"""

    def process_docs(self, docs: list[dict], query: str) -> dict:
        # Ensure fresh run
        if self.indexes_dir.exists():
            shutil.rmtree(self.indexes_dir)
        self.indexes_dir.mkdir(parents=True, exist_ok=True)

        topics_json = {}
        scratch_pad = ""
        batch_size = getattr(self.config, "indexer_batch_size", 5)

        system_prompt = (
            f"You are an advanced hierarchical information indexer processing a batch of {batch_size} documents.\n\n"
            f"## YOUR TASKS\n\n"
            f"### 1. TOPIC DEDUPLICATION (DO THIS FIRST)\n"
            f"Before adding any NEW topic, scan the existing topics hierarchy.\n"
            f"If document content logically belongs under an existing topic, place it there as a subtopic.\n"
            f"Do NOT create parallel top-level topics for the same domain.\n"
            f"Example: 'Chlorophyll B absorption' -> nest under existing 'Light Reactions' > 'Pigments', NOT as new top-level 'Chlorophyll B'.\n"
            f"Maximum hierarchy depth is {self.max_depth}.\n\n"
            f"### 2. EXTRACT INFORMATION BLOCKS\n"
            f"- A path is a list of topic names matching the JSON hierarchy, e.g. ['Topic 1', 'Subtopic 1'].\n"
            f"- Each block must include source attribution at the top: '### Source: [Title](URL)'.\n"
            f"- Preserve full substantive content. Do NOT truncate or summarize at this stage. Use long markdown.\n\n"
            f"### 3. UPDATE SCRATCH PAD (STRUCTURED FORMAT)\n"
            f"The scratch pad must follow this exact structure:\n"
            f"## Coverage Status\n"
            f"- [Topic Path]: status (covered/partial/gap)\n"
            f"## Key Statistics Found\n"
            f"- [Fact]: value from [Source Title]\n"
            f"## Cross-References Identified\n"
            f"- [Topic A] relates to [Topic B] because: explanation\n"
            f"## Quality Notes\n"
            f"- [Source Title]: RELIABLE — reason / CAUTION — reason\n"
            f"## Remaining Gaps\n"
            f"- [Topic]: not yet covered\n\n"
            f"## RESPONSE FORMAT\n"
            f"Return strictly valid JSON (no markdown, no code fences):\n"
            f'{{\n  "updated_topics_hierarchy": '
            f'{{ "Topic 1": {{"Subtopic 1": {{}}}}, "Topic 2": {{}} }},\n'
            f'  "extracted_information": [\n'
            f'     {{\n'
            f'       "path": ["Topic 1", "Subtopic 1"],\n'
            f'       "content": "### Source: [Title](URL)\\n\\nDetailed text from document..."\n'
            f'     }}\n'
            f'  ],\n'
            f'  "updated_scratch_pad": "Structured scratch pad content."\n'
            f"}}"
        )

        logger.info(
            "Starting indexing of %s documents (batch size=%s)...",
            len(docs),
            batch_size,
        )
        for batch_start in range(0, len(docs), batch_size):
            batch = docs[batch_start:batch_start + batch_size]
            logger.info(
                "Processing batch %s-%s of %s",
                batch_start + 1,
                batch_start + len(batch),
                len(docs),
            )

            prompt = self._build_prompt(query, batch, topics_json, scratch_pad)
            try:
                response = self.llm.json(
                    prompt,
                    system=system_prompt,
                    max_tokens=8000,
                )

                if "updated_topics_hierarchy" in response:
                    topics_json = response["updated_topics_hierarchy"]

                if "updated_scratch_pad" in response:
                    scratch_pad = response["updated_scratch_pad"]

                for item in response.get("extracted_information", []):
                    path = item.get("path", [])
                    content = item.get("content", "")

                    if not path or not content:
                        continue

                    # Limit to max depth
                    path = path[:self.max_depth]

                    # Sanitize path elements
                    safe_path_elements = [sanitize_dirname(p) or "unknown" for p in path]

                    target_dir = self.indexes_dir.joinpath(*safe_path_elements)
                    target_dir.mkdir(parents=True, exist_ok=True)

                    info_file = target_dir / "information.md"
                    # Include source references for all documents in batch
                    source_header = "\n".join(
                        f"### Source: [{d.get('title', 'Untitled')}]({d.get('url', '')})"
                        for d in batch
                    )
                    with open(info_file, "a", encoding="utf-8") as f:
                        f.write(f"\n{source_header}\n\n{content}\n")

            except Exception as e:
                logger.warning("Error processing batch starting at %s: %s", batch_start, e)

        # Save final state for debugging & usage
        workspace = Path(self.config.workspace_dir)
        workspace.mkdir(parents=True, exist_ok=True)
        with open(workspace / "scratch_pad.md", "w", encoding="utf-8") as f:
            f.write(scratch_pad)

        with open(workspace / "topics.json", "w", encoding="utf-8") as f:
            json.dump(topics_json, f, indent=2)

        return topics_json
