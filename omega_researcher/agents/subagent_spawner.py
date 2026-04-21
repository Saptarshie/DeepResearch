"""SubagentSpawner — parallel recursive sub-agents with shared INDEXES/."""
from __future__ import annotations
import asyncio
import copy
import uuid
from omega_researcher.config import Config
from omega_researcher.schemas import SubAgentTask, SubAgentResult, ResearchState


class SubagentSpawner:
    """
    Spawns parallel sub-agents for independent subtopics.
    Each sub-agent runs its own PAC loop recursively.
    Respects SPAWNING_DEPTH_LIMIT = 3.

    Depth semantics:
    - depth=0: root research agent
    - depth=1: first-level subagents
    - depth=2: second-level subagents
    - depth=3: leaf agents (cannot spawn further)
    """

    def __init__(self, config: Config, llm, index_manager, skill_loader):
        self.config = config
        self.llm = llm
        self.index_manager = index_manager
        self.skill_loader = skill_loader

    async def spawn_for_subquestions(
        self,
        subquestions: list[str],
        parent_state: ResearchState,
    ) -> list[SubAgentResult]:
        """Spawn one sub-agent per subquestion (up to max_subagents), run in parallel."""
        current_depth = parent_state.depth

        if current_depth >= self.config.SPAWNING_DEPTH_LIMIT:
            print(f"[spawner] Depth limit {self.config.SPAWNING_DEPTH_LIMIT} reached — not spawning")
            return []

        tasks = [
            SubAgentTask(
                task_id=str(uuid.uuid4())[:8],
                subtopic=sq,
                parent_depth=current_depth,
                config_overrides={
                    "max_docs": self.config.subagent_max_docs,
                    "max_pac_cycles": 5,
                    "actor_max_actions_per_cycle": 3,
                },
            )
            for sq in subquestions[: self.config.max_subagents]
        ]

        print(f"[spawner] Spawning {len(tasks)} sub-agents at depth {current_depth + 1}")

        results = await asyncio.gather(
            *[self._run_subagent(task, parent_state) for task in tasks],
            return_exceptions=True,
        )

        valid = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                print(f"[spawner] Sub-agent {tasks[i].task_id} failed: {r}")
                valid.append(SubAgentResult(
                    task_id=tasks[i].task_id,
                    subtopic=tasks[i].subtopic,
                    docs=[], topics_json={}, scratch_pad="",
                    report_section="",
                    success=False, error=str(r),
                ))
            else:
                valid.append(r)

        return valid

    async def _run_subagent(
        self, task: SubAgentTask, parent_state: ResearchState
    ) -> SubAgentResult:
        """Run a single sub-agent with its own Orchestrator instance."""
        from omega_researcher.orchestrator import Orchestrator

        # Build child config with overrides
        child_cfg = copy.copy(self.config)
        for k, v in task.config_overrides.items():
            setattr(child_cfg, k, v)

        # Subagent inherits parent rolling summary (knows what's been done)
        inherited_summary = parent_state.rolling_summary

        try:
            timeout = self.config.subagent_timeout
            orchestrator = Orchestrator(
                config=child_cfg,
                depth=task.parent_depth + 1,
                # CRITICAL: share same INDEXES/ → cross-agent INDEX-AS-YOU-GO
                shared_indexes_dir=self.config.indexes_dir,
                initial_rolling_summary=inherited_summary,
            )

            state = await asyncio.wait_for(
                orchestrator.run(query=task.subtopic, file_paths=[]),
                timeout=timeout,
            )

            return SubAgentResult(
                task_id=task.task_id,
                subtopic=task.subtopic,
                docs=state.docs,
                topics_json=state.topics_json,
                scratch_pad=state.scratch_pad,
                report_section=state.rolling_summary,
                success=True,
            )

        except asyncio.TimeoutError:
            return SubAgentResult(
                task_id=task.task_id, subtopic=task.subtopic,
                docs=[], topics_json={}, scratch_pad="",
                report_section="[Subagent timed out]",
                success=False, error="Timeout",
            )
        except Exception as e:
            return SubAgentResult(
                task_id=task.task_id, subtopic=task.subtopic,
                docs=[], topics_json={}, scratch_pad="",
                report_section=f"[Subagent error: {e}]",
                success=False, error=str(e),
            )

    def merge_results(
        self, parent_state: ResearchState, results: list[SubAgentResult]
    ) -> ResearchState:
        """Merge sub-agent results back into parent state."""
        for result in results:
            if result.success:
                parent_state.docs.extend(result.docs)
                _deep_merge(parent_state.topics_json, result.topics_json)
                parent_state.scratch_pad += (
                    f"\n\n## SubAgent: {result.subtopic}\n{result.scratch_pad}"
                )
                parent_state.spawned_subagent_ids.append(result.task_id)
        return parent_state


def _deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _deep_merge(base[k], v)
        else:
            base[k] = v
    return base
