"""Orchestrator — the PAC loop coordinator."""
from __future__ import annotations
import asyncio
import time
from pathlib import Path
from typing import Optional

from omega_researcher.config import Config
from omega_researcher.schemas import ResearchState, IngestedDocument, DocumentSource
from omega_researcher.llm_client import LLMClient
from omega_researcher.memory.scratch_pad import ScratchPad
from omega_researcher.memory.rolling_summary import RollingSummary
from omega_researcher.memory.index_manager import IndexManager
from omega_researcher.skills.skill_loader import SkillLoader
from omega_researcher.agents.planner_agent import PlannerAgent
from omega_researcher.agents.actor_agent import ActorAgent
from omega_researcher.agents.critic_agent import CriticAgent
from omega_researcher.synthesizer.synthesizer import Synthesizer


class Orchestrator:
    """
    Planner → Actor → Critic PAC loop coordinator.

    Usage:
        orch = Orchestrator(config, depth=0)
        state = await orch.run(query="...", file_paths=["paper.pdf", "data.csv"])
        # report is written to report-content.md
    """

    def __init__(
        self,
        config: Optional[Config] = None,
        depth: int = 0,
        shared_indexes_dir: Optional[str] = None,
        initial_rolling_summary: str = "",
    ):
        self.config = config or Config()
        self.depth = depth

        # Share parent INDEXES/ dir if provided (subagent scenario)
        if shared_indexes_dir:
            self.config.indexes_dir = shared_indexes_dir

        # ─── Core services ────────────────────────────────────────────────
        self.llm = LLMClient(self.config)
        self.scratch_pad = ScratchPad(self.config.scratch_pad_path)
        self.rolling_summary = RollingSummary(self.config, llm_client=self.llm)
        self.index_manager = IndexManager(self.config)
        self.skill_loader = SkillLoader(self.config)

        # Inject inherited rolling summary (from parent agent)
        if initial_rolling_summary:
            self.rolling_summary.update(
                f"[Inherited from parent agent]\n{initial_rolling_summary}",
                context="inherited",
            )

        # ─── Agents ───────────────────────────────────────────────────────
        self.planner = PlannerAgent(self.config, self.llm, self.skill_loader)
        self.critic = CriticAgent(self.config, self.llm)

        # MCP tools (built lazily to avoid Docker import on startup)
        self._mcp_tools = None

        self.actor = ActorAgent(
            config=self.config,
            llm=self.llm,
            index_manager=self.index_manager,
            scratch_pad=self.scratch_pad,
            rolling_summary=self.rolling_summary,
            skill_loader=self.skill_loader,
            mcp_tools=None,  # patched below once tools are built
        )

        self.synthesizer = Synthesizer(self.llm, self.config)

    # ── Main entry point ──────────────────────────────────────────────────────

    async def run(
        self,
        query: str,
        file_paths: Optional[list[str]] = None,
    ) -> ResearchState:
        """Full PAC loop: ingest → plan → actor/critic cycles → synthesize."""
        start_time = time.time()
        file_paths = file_paths or []

        print(f"\n{'='*60}")
        print(f"[orchestrator] Query: {query}")
        print(f"[orchestrator] Depth: {self.depth} | Files: {len(file_paths)}")
        print(f"{'='*60}\n")

        # ── Phase 1: Build MCP tool registry ─────────────────────────────
        self._build_mcp_tools()

        # ── Phase 2: Ingest uploaded files ───────────────────────────────
        pre_ingested = []
        if file_paths:
            pre_ingested = await asyncio.get_event_loop().run_in_executor(
                None, self._ingest_files, file_paths
            )

        # ── Phase 3: Plan ─────────────────────────────────────────────────
        print("[orchestrator] Planning...")
        plan = self.planner.make_plan(query, pre_ingested_docs=pre_ingested)

        state = ResearchState(
            query=query,
            plan=plan,
            docs=list(pre_ingested),
            depth=self.depth,
            active_skills=plan.active_skills,
        )

        # Index pre-ingested docs immediately (INDEX-AS-YOU-GO)
        for doc in pre_ingested:
            self._index_one(doc, state)

        # ── Phase 4: PAC Loop ─────────────────────────────────────────────
        print(f"[orchestrator] Starting PAC loop (max_cycles={self.config.max_pac_cycles})")
        for cycle in range(self.config.max_pac_cycles):
            state.pac_cycle = cycle
            print(f"\n[orchestrator] --- PAC Cycle {cycle + 1} ---")

            # Actor
            state = await self.actor.run_cycle(state)

            # Critic (every critique_batch_size docs or last cycle)
            if (
                len(state.docs) % self.config.critique_batch_size == 0
                or len(state.docs) == 0
            ):
                print(f"[orchestrator] Critic evaluating ({len(state.docs)} docs)...")
                coverage = self.critic.evaluate(query, state)
                state.coverage_scores = coverage.coverage_scores

                print(
                    f"[orchestrator] Coverage: {coverage.overall_coverage:.0%} | "
                    f"Missing: {coverage.missing_subtopics[:2]}"
                )

                # Inject followup queries into plan
                if coverage.followup_queries:
                    state.plan.queries.extend(coverage.followup_queries)

                if not coverage.should_research_more:
                    print(
                        f"[orchestrator] Coverage threshold {self.config.coverage_threshold:.0%} reached — stopping"
                    )
                    break

            # Safety: stop if no more queries and no plan for subagents
            if not state.plan.queries and not state.plan.spawn_subagents:
                print("[orchestrator] No more queries, ending loop early")
                break

        # ── Phase 5: Synthesize ───────────────────────────────────────────
        state.rolling_summary = self.rolling_summary.get()
        state.scratch_pad = self.scratch_pad.read()

        print("\n[orchestrator] Synthesizing final report...")
        report = self.synthesizer.synthesize(query, state)
        print(f"[orchestrator] Report written ({len(report):,} chars)")

        # ── Phase 6: Post-eval (non-blocking) ────────────────────────────
        duration = time.time() - start_time
        print(f"[orchestrator] Total duration: {duration:.1f}s")
        asyncio.create_task(self._post_eval(query, plan, report, state, duration))

        return state

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _build_mcp_tools(self):
        from omega_researcher.mcp.mcp_server import build_tool_registry
        self._mcp_tools = build_tool_registry(
            config=self.config,
            llm=self.llm,
            index_manager=self.index_manager,
            skill_loader=self.skill_loader,
            scratch_pad=self.scratch_pad,
            rolling_summary=self.rolling_summary,
        )
        # Inject into actor
        self.actor.mcp_tools = self._mcp_tools

    def _ingest_files(self, file_paths: list[str]) -> list[IngestedDocument]:
        """Synchronous ingestion — called from executor to avoid blocking event loop."""
        from omega_researcher.ingestion.data_reader import DataReader, CSV_EXTS, EXCEL_EXTS

        results = []
        data_reader = DataReader(self.config)

        for path_str in file_paths:
            path = Path(path_str)
            ext = path.suffix.lower()

            if not path.exists():
                print(f"[orchestrator] File not found: {path}")
                continue

            size_mb = path.stat().st_size / (1024 * 1024)
            if size_mb > self.config.max_file_size_mb:
                print(f"[orchestrator] File too large ({size_mb:.1f}MB), skipping: {path}")
                continue

            try:
                if ext in CSV_EXTS | EXCEL_EXTS:
                    doc = data_reader.to_ingested_document(str(path))
                else:
                    from omega_researcher.ingestion.docling_parser import DoclingParser, SUPPORTED_FORMATS
                    if ext not in SUPPORTED_FORMATS:
                        print(f"[orchestrator] Unsupported format {ext}, skipping: {path}")
                        continue
                    parser = DoclingParser(self.config)
                    doc = parser.parse(str(path))

                results.append(doc)
                print(f"[orchestrator] Ingested: {doc.title} ({doc.source_type.value})")

            except Exception as e:
                print(f"[orchestrator] Ingestion failed for {path}: {e}")

        return results

    def _index_one(self, doc: IngestedDocument, state: ResearchState) -> None:
        """Index one document immediately, update state."""
        try:
            result = self.index_manager.index_document(
                doc, state.query, self.llm, self.scratch_pad.read()
            )
            if result.get("scratch_pad_update"):
                self.scratch_pad.append("Global Notes", result["scratch_pad_update"])
            state.topics_json = result["topics_json"]
        except Exception as e:
            print(f"[orchestrator] Index failed for {doc.title}: {e}")

    async def _post_eval(self, query, plan, report, state, duration):
        """Non-blocking post-evaluation."""
        try:
            from omega_researcher.agents.meta_agent import MetaAgent
            meta = MetaAgent(self.config)
            await meta.post_eval(query, plan, report, state, duration)
        except Exception as e:
            print(f"[orchestrator] post_eval error: {e}")


# ── Backward-compatible entry point ───────────────────────────────────────────

async def deep_research(
    query: str,
    config: Optional[Config] = None,
    file_paths: Optional[list[str]] = None,
) -> str:
    """
    Main API. Drop-in replacement for original deep_search().

    Returns the final report (string).
    Also writes to report-content.md.
    """
    orch = Orchestrator(config=config or Config())
    state = await orch.run(query=query, file_paths=file_paths or [])
    report_path = Path("report-content.md")
    if report_path.exists():
        return report_path.read_text(encoding="utf-8")
    return state.rolling_summary or "[No report generated]"
