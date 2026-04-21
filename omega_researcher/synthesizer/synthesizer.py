"""Enhanced Synthesizer — accepts ResearchState, uses rolling_summary and scratch_pad."""
from __future__ import annotations
from omega_researcher.config import Config
from omega_researcher.schemas import ResearchState


class Synthesizer:
    """
    Enhanced synthesizer that takes the full ResearchState.
    - Most docs already indexed by actor (INDEX-AS-YOU-GO)
    - Uses rolling_summary as initial context for report builder
    - Uses scratch_pad insights for key facts
    """

    def __init__(self, llm, config: Config):
        self.llm = llm
        self.config = config

    def synthesize(self, topic: str, state: ResearchState) -> str:
        """Generate final report from fully-indexed state."""
        print(f"\n[synthesizer] Building overviews for {self.config.indexes_dir}...")

        # 1. Build overviews (post-order DFS over INDEXES/ tree)
        from omega_researcher.synthesizer.overview_builder import OverviewBuilder
        ob = OverviewBuilder(self.llm, self.config)
        ob.build_overview(self.config.indexes_dir)

        # 2. Build final report with rolling_summary as initial context
        print("[synthesizer] Building final report...")
        from omega_researcher.synthesizer.report_builder import ReportBuilder
        rb = ReportBuilder(self.llm, self.config)

        report = rb.build_report(
            topics_json=state.topics_json,
            rolling_summary=state.rolling_summary,
            scratch_pad=state.scratch_pad,
        )

        return report
