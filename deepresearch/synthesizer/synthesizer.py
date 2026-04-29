from __future__ import annotations

from deepresearch.config import Config
from deepresearch.llm_client import LLMClient
from deepresearch.synthesizer.indexer import Indexer


class Synthesizer:
    def __init__(self, llm_client: LLMClient, config: Config):
        self.llm = llm_client
        self.config = config

    def synthesize(self, topic: str, docs: list[dict]) -> str:
        indexer = Indexer(self.llm, self.config)
        topics_json = indexer.process_docs(docs, topic)

        from deepresearch.synthesizer.overview_builder import OverviewBuilder
        ob = OverviewBuilder(self.llm, self.config)
        ob.build_overview(self.config.indexes_dir)

        from deepresearch.synthesizer.report_builder import ReportBuilder
        rb = ReportBuilder(self.llm, self.config)
        report = rb.build_report(topics_json)

        return report
