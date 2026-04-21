"""Phase 2 import-chain test — verify all modules load without errors."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

def test_imports():
    # Config + Schemas
    from omega_researcher.config import Config
    from omega_researcher.schemas import (
        IngestedDocument, ResearchState, ResearchPlan,
        CoverageReport, Experience, SubAgentTask, SubAgentResult,
        Skill, DocumentSource, ActionResult,
    )
    print("[PASS] config + schemas")

    # Memory
    from omega_researcher.memory.scratch_pad import ScratchPad
    from omega_researcher.memory.rolling_summary import RollingSummary
    from omega_researcher.memory.experiences import ExperienceLogger
    from omega_researcher.memory.index_manager import IndexManager
    print("[PASS] memory modules")

    # Search
    from omega_researcher.search.index_search import IndexSearch
    print("[PASS] search.index_search")

    # Skills
    from omega_researcher.skills.skill_loader import SkillLoader
    from omega_researcher.skills.skill_creator import SkillCreator
    print("[PASS] skills modules")

    # Ingestion (no heavy imports triggered yet)
    from omega_researcher.ingestion.data_reader import DataReader
    from omega_researcher.ingestion.web_fetcher import WebFetcher
    print("[PASS] ingestion modules (lazy docling OK)")

    # LLM client
    from omega_researcher.llm_client import LLMClient, fix_json_escapes
    assert fix_json_escapes('{"key": "val"}') == '{"key": "val"}'
    assert fix_json_escapes('```json\n{"a":1}\n```') == '{"a":1}'
    print("[PASS] llm_client + fix_json_escapes")

    # Agents
    from omega_researcher.agents.planner_agent import PlannerAgent
    from omega_researcher.agents.critic_agent import CriticAgent
    from omega_researcher.agents.actor_agent import ActorAgent
    from omega_researcher.agents.subagent_spawner import SubagentSpawner
    from omega_researcher.agents.meta_agent import MetaAgent
    print("[PASS] all agents")

    # MCP tools
    from omega_researcher.mcp.tools.code_executor import CodeExecutor
    from omega_researcher.mcp.tools.data_tools import DataTools
    from omega_researcher.mcp.tools.search_tools import SearchTools
    from omega_researcher.mcp.tools.file_tools import FileTools
    from omega_researcher.mcp.tools.skill_tools import SkillTools
    from omega_researcher.mcp.mcp_server import build_tool_registry
    print("[PASS] mcp tools")

    # Synthesizer
    from omega_researcher.synthesizer.overview_builder import OverviewBuilder
    from omega_researcher.synthesizer.report_builder import ReportBuilder
    from omega_researcher.synthesizer.synthesizer import Synthesizer
    print("[PASS] synthesizer modules")

    # Orchestrator (triggers all lazy imports)
    from omega_researcher.orchestrator import Orchestrator, deep_research
    print("[PASS] orchestrator")

    # Top-level package
    from omega_researcher import Config as Cfg
    assert Cfg is Config
    print("[PASS] omega_researcher package")


def test_instantiation():
    """Test that all key classes instantiate without side-effects."""
    from omega_researcher.config import Config
    from omega_researcher.memory.scratch_pad import ScratchPad
    from omega_researcher.memory.index_manager import IndexManager
    from omega_researcher.search.index_search import IndexSearch
    from omega_researcher.skills.skill_loader import SkillLoader

    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = Config()
        cfg.indexes_dir = os.path.join(tmpdir, "IDX")
        cfg.scratch_pad_path = os.path.join(tmpdir, "sp.md")
        cfg.rolling_summary_path = os.path.join(tmpdir, "rs.md")
        cfg.experiences_path = os.path.join(tmpdir, "exp.md")
        cfg.skills_dir = os.path.join(tmpdir, "SKILLS")

        sp = ScratchPad(cfg.scratch_pad_path)
        im = IndexManager(cfg)
        ix = IndexSearch(cfg)
        sl = SkillLoader(cfg)

        assert sp.read() == ""
        assert isinstance(im.get_topics(), dict)   # may load existing topics.json from cwd
        assert ix.search("test") == []
        assert sl.load_all() == []

        print("[PASS] all core classes instantiate cleanly")


if __name__ == "__main__":
    test_imports()
    test_instantiation()
    print("\n[OK] ALL PHASE 2 IMPORT TESTS PASSED")
