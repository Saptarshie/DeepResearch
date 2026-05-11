from __future__ import annotations

from collections.abc import Callable
from typing import Any

from deepresearch.config import Config
from deepresearch.llm_client import LLMClient
from deepresearch.synthesizer.indexer import Indexer


class Synthesizer:
    def __init__(self, llm_client: LLMClient, config: Config):
        self.llm = llm_client
        self.config = config

    def synthesize(
        self,
        topic: str,
        docs: list[dict],
        progress_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ) -> str:
        def emit(event_type: str, data: dict[str, Any] | None = None):
            if progress_callback:
                progress_callback(event_type, data or {})

        indexer = Indexer(self.llm, self.config)
        topics_json = indexer.process_docs(docs, topic, progress_callback=progress_callback)

        emit("synth_overview", {"message": "Building topic overview..."})
        from deepresearch.synthesizer.overview_builder import OverviewBuilder
        ob = OverviewBuilder(self.llm, self.config)
        ob.build_overview(self.config.indexes_dir)

        emit("synth_report_start", {"message": "Starting report generation..."})
        from deepresearch.synthesizer.report_builder import ReportBuilder
        rb = ReportBuilder(self.llm, self.config)
        report = rb.build_report(topics_json, progress_callback=progress_callback)

        emit("synth_report_complete", {"message": "Report generation complete."})
        return report
