import json
import logging
import shutil
from collections.abc import Callable
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

    def process_docs(
        self,
        docs: list[dict],
        query: str,
        progress_callback: Callable[[str, dict], None] | None = None,
    ) -> dict:
        def emit(event_type: str, data: dict | None = None):
            if progress_callback:
                progress_callback(event_type, data or {})

        # Ensure fresh run
        if self.indexes_dir.exists():
            shutil.rmtree(self.indexes_dir)
        self.indexes_dir.mkdir(parents=True, exist_ok=True)

        topics_json = {}
        scratch_pad = ""
        batch_size = getattr(self.config, "indexer_batch_size", 5)

        system_prompt = (
            f"You are an advanced hierarchical information indexer processing a batch of documents.\n\n"
            f"## YOUR TASKS\n\n"
            f"### 1. AGGRESSIVE TOPIC DEDUPLICATION (CRITICAL)\n"
            f"Scan the existing topics hierarchy. You must prevent narrative fragmentation.\n"
            f"If a document discusses a policy, event, or concept that ALREADY exists in the hierarchy, you MUST merge it into the existing path.\n"
            f"DO NOT create parallel, synonymous, or slightly re-worded top-level topics (e.g., do not have both 'Fiscal Policy Impact' and 'Impact of Fiscal Bills'). Merge them.\n\n"
            f"### 2. EXTRACT INFORMATION BLOCKS (FOCUS ON CAUSALITY)\n"
            f"- Extract substantive content, paying special attention to cause-and-effect relationships, statistics, and transmission mechanisms.\n"
            f"- Each block must include source attribution: '### Source: [Title](URL)'.\n\n"
            f"### 3. UPDATE SCRATCH PAD (STRUCTURED FORMAT)\n"
            f"## Coverage Status\n"
            f"- [Topic Path]: status (covered/partial/gap)\n"
            f"## Causal Chains Identified (The 'Why')\n"
            f"- [Trigger] leads to [Outcome] because: [Explanation from source]\n"
            f"## Cross-References Identified\n"
            f"- [Topic A] strictly relates to [Topic B]\n\n"
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

        total_batches = (len(docs) + batch_size - 1) // batch_size
        logger.info(
            "Starting indexing of %s documents (batch size=%s)...",
            len(docs),
            batch_size,
        )
        for batch_start in range(0, len(docs), batch_size):
            batch = docs[batch_start:batch_start + batch_size]
            batch_num = batch_start // batch_size + 1
            logger.info(
                "Processing batch %s-%s of %s",
                batch_start + 1,
                batch_start + len(batch),
                len(docs),
            )
            emit("synth_indexer_batch", {
                "current_batch": batch_num,
                "total_batches": total_batches,
                "docs_in_batch": len(batch),
                "message": f"Indexing batch {batch_num}/{total_batches} ({len(batch)} docs)...",
            })

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

        emit("synth_indexer_complete", {
            "topics_count": len(topics_json),
            "message": f"Indexing complete — {len(topics_json)} top-level topics extracted.",
        })
        return topics_json
