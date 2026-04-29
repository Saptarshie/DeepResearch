from deepresearch.config import Config
from deepresearch.llm_client import LLMClient
from deepresearch.synthesizer.indexer import Indexer

class Synthesizer:
    def __init__(self, llm_client: LLMClient, config: Config | None = None):
        self.llm = llm_client
        self.config = config or Config()

    def synthesize(self, topic: str, docs: list[dict]) -> str:
        # 1. Parse Docs and Index
        indexer = Indexer(self.llm, self.config)
        topics_json = indexer.process_docs(docs, topic)
        
        # 2. Build Overviews
        from deepresearch.synthesizer.overview_builder import OverviewBuilder
        ob = OverviewBuilder(self.llm, self.config)
        ob.build_overview(self.config.indexes_dir)
        
        # 3. Final Report Builder
        from deepresearch.synthesizer.report_builder import ReportBuilder
        rb = ReportBuilder(self.llm, self.config)
        report = rb.build_report(topics_json)
        
        return report
