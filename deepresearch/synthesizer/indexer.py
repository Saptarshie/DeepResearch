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

    def process_docs(self, docs: list[dict], query: str) -> dict:
        # Ensure fresh run
        if self.indexes_dir.exists():
            shutil.rmtree(self.indexes_dir)
        self.indexes_dir.mkdir(parents=True, exist_ok=True)

        topics_json = {}
        scratch_pad = ""

        system_prompt = f"""You are an advanced hierarchical information indexer.
You are given:
- The user's query
- A document's content
- The current topics hierarchy (JSON where keys are topics, values are subtopic dicts)
- The current scratch pad

Your job is to:
1. Update the topics hierarchy with any NEW relevant topics from the document. The maximum depth of the hierarchy is {self.max_depth}. Keep keys short and descriptive.
2. Extract specific information blocks from the document to place in the appropriate topic/subtopic paths. 
   - A path is a list of topic names corresponding to the JSON hierarchy. (e.g. ["Artificial Intelligence", "Neural Networks"])
   - IMPORTANT: Only output the information blocks that belong to the new hierarchy.
3. Update the global scratch pad with any important insight, global context, or summary.

Respond strictly in the following JSON format:
{{
  "updated_topics_hierarchy": {{ "Topic 1": {{"Subtopic 1": {{}}}}, "Topic 2": {{}} }},
  "extracted_information": [
     {{
       "path": ["Topic 1", "Subtopic 1"],
       "content": "Detailed text from document relevant to this path. Should be long markdown."
     }}
  ],
  "updated_scratch_pad": "The new content for the scratch pad."
}}"""

        logger.info("Starting indexing of %s documents...", len(docs))
        for i, doc in enumerate(docs, 1):
            title = doc.get("title", "Untitled")
            text = doc.get("text", "")
            url = doc.get("url", "")
            logger.info("Processing doc %s/%s: %s", i, len(docs), title)

            prompt = f"""
## User Query
{query}

## Document Info
Title: {title}
URL: {url}

## Document Content
{text[:10000]}

## Current Topics Hierarchy
{json.dumps(topics_json, indent=2)}

## Current Scratch Pad
{scratch_pad}
"""
            try:
                response = self.llm.json(
                    prompt,
                    system=system_prompt,
                    provider="anthropic",
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
                    with open(info_file, "a", encoding="utf-8") as f:
                        f.write(f"\n### Source: [{title}]({url})\n\n{content}\n")

            except Exception as e:
                logger.warning("Error processing document: %s", e)

        # Save final state for debugging & usage
        workspace = Path(self.config.workspace_dir)
        workspace.mkdir(parents=True, exist_ok=True)
        with open(workspace / "scratch_pad.md", "w", encoding="utf-8") as f:
            f.write(scratch_pad)

        with open(workspace / "topics.json", "w", encoding="utf-8") as f:
            json.dump(topics_json, f, indent=2)

        return topics_json
