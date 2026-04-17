import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from deepresearch.config import Config
from deepresearch.llm_client import LLMClient
from deepresearch.synthesizer.indexer import Indexer

async def main():
    config = Config()
    llm = LLMClient(config)
    indexer = Indexer(llm, config)
    
    docs = [
        {"title": "Doc 1", "url": "http://doc1", "text": "This is about Neural Networks and how they relate to AI."},
        {"title": "Doc 2", "url": "http://doc2", "text": "This is about Transformers, an advanced Neural Network architecture used in LLMs."},
    ]
    query = "What is the relationship between AI, Neural Networks, and Transformers?"
    
    # topics = indexer.process_docs(docs, query)
    # print("Final Topics:", topics)
    
    from deepresearch.synthesizer.overview_builder import OverviewBuilder
    from pathlib import Path
    ob = OverviewBuilder(llm, config)
    # ob.build_overview(Path(config.indexes_dir))
    print("Overview building complete.")
    
    from deepresearch.synthesizer.report_builder import ReportBuilder
    import json
    rb = ReportBuilder(llm, config)
    with open("topics.json", "r", encoding="utf-8") as f:
        topics_json = json.load(f)
    report = rb.build_report(topics_json)
    print("\n\nFINAL REPORT:\n\n", report)

if __name__ == "__main__":
    asyncio.run(main())
