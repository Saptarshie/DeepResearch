"""Test Phase 1A — Config, Schemas, Memory, IndexSearch."""
import sys, os
from pathlib import Path

# Ensure omega_researcher is importable
# tests/ -> omega_researcher/ -> deepresearch/  (3 levels up)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import tempfile, shutil

def test_config():
    from omega_researcher.config import Config
    cfg = Config()
    assert cfg.max_indexer_depth == 3
    assert cfg.SPAWNING_DEPTH_LIMIT == 3
    assert cfg.coverage_threshold == 0.85
    assert cfg.max_pac_cycles == 20
    assert cfg.indexes_dir == "INDEXES"
    print("[PASS] Config loads with all fields")

def test_schemas():
    from omega_researcher.schemas import (
        IngestedDocument, DocumentSource, Skill, ResearchPlan,
        ResearchState, ActionResult, SubAgentTask, SubAgentResult,
        CoverageReport, Experience,
    )
    doc = IngestedDocument(
        source_type=DocumentSource.WEB,
        source_path="http://example.com",
        title="Test",
        text="Hello world",
    )
    assert doc.source_type == DocumentSource.WEB
    assert doc.tables == []
    
    plan = ResearchPlan(topic="test", subquestions=["q1"], queries=["q1"])
    state = ResearchState(query="test", plan=plan)
    assert state.depth == 0
    assert state.pac_cycle == 0
    
    exp = Experience(
        timestamp="2026-01-01", query="test", outcome="success",
        coverage_achieved=0.9, skills_used=[], tools_used=["web_search"],
        what_worked="everything", what_failed="nothing",
        suggestions="none", subagents_spawned=0, total_docs=5,
        duration_seconds=10.0,
    )
    assert exp.outcome == "success"
    print("[PASS] All schemas instantiate correctly")

def test_scratch_pad():
    from omega_researcher.memory.scratch_pad import ScratchPad
    
    with tempfile.TemporaryDirectory() as tmpdir:
        sp_path = os.path.join(tmpdir, "test_scratch.md")
        sp = ScratchPad(path=sp_path)
        
        # Write and read
        sp.write("Global Notes", "This is a test note.")
        assert "test note" in sp.read("Global Notes")
        
        # Append
        sp.append("Global Notes", "Another note.")
        content = sp.read("Global Notes")
        assert "test note" in content
        assert "Another note" in content
        
        # Read all
        full = sp.read()
        assert "Global Notes" in full
        
        # Persistence — reload from disk
        sp2 = ScratchPad(path=sp_path)
        assert "test note" in sp2.read("Global Notes")
        
        # Clear
        sp.clear()
        assert sp.read("Global Notes") == ""
        
        print("[PASS] ScratchPad write/append/read/persist/clear")

def test_rolling_summary():
    from omega_researcher.memory.rolling_summary import RollingSummary
    from omega_researcher.config import Config
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = Config()
        cfg.rolling_summary_path = os.path.join(tmpdir, "test_rs.md")
        cfg.rolling_summary_max_tokens = 50  # Force compression quickly
        
        rs = RollingSummary(cfg, llm_client=None)  # No LLM — will truncate
        
        rs.update("Discovery 1: AI is cool", "test query")
        assert "Discovery 1" in rs.get()
        
        # Force compression by adding lots of text
        for i in range(20):
            rs.update(f"Discovery {i}: " + "x" * 200, "test query")
        
        # Should have been truncated (no LLM available)
        text = rs.get()
        assert len(text) > 0
        
        # Reset
        rs.reset()
        assert rs.get() == ""
        
        print("[PASS] RollingSummary update/compress/reset")

def test_experiences():
    from omega_researcher.memory.experiences import ExperienceLogger
    from omega_researcher.schemas import Experience
    from omega_researcher.config import Config
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = Config()
        cfg.experiences_path = os.path.join(tmpdir, "test_exp.md")
        
        logger = ExperienceLogger(cfg)
        
        exp1 = Experience(
            timestamp="2026-01-01T00:00:00", query="test query 1",
            outcome="success", coverage_achieved=0.9,
            skills_used=["data_analysis"], tools_used=["web_search"],
            what_worked="search was great", what_failed="nothing",
            suggestions="none", subagents_spawned=0,
            total_docs=10, duration_seconds=30.0,
        )
        exp2 = Experience(
            timestamp="2026-01-02T00:00:00", query="test query 2",
            outcome="failure", coverage_achieved=0.3,
            skills_used=[], tools_used=["web_search"],
            what_worked="initial search", what_failed="ran out of docs",
            suggestions="use more queries", subagents_spawned=1,
            total_docs=3, duration_seconds=15.0,
        )
        
        logger.log(exp1)
        logger.log(exp2)
        
        all_exp = logger.read_all()
        assert len(all_exp) == 2
        assert all_exp[0].outcome == "success"
        
        failures = logger.read_failures()
        assert len(failures) == 1
        assert failures[0].query == "test query 2"
        
        matched = logger.read_for_query_type(["test"])
        assert len(matched) == 2
        
        assert logger.count() == 2
        
        # Check markdown file exists
        md_path = Path(cfg.experiences_path)
        assert md_path.exists()
        md_content = md_path.read_text(encoding="utf-8")
        assert "test query 1" in md_content
        
        print("[PASS] ExperienceLogger log/read_all/read_failures/count")

def test_index_search():
    from omega_researcher.search.index_search import IndexSearch
    from omega_researcher.config import Config
    
    with tempfile.TemporaryDirectory() as tmpdir:
        cfg = Config()
        cfg.indexes_dir = os.path.join(tmpdir, "INDEXES")
        
        # Build a tiny index tree
        idx = Path(cfg.indexes_dir)
        (idx / "AI" / "Neural_Networks").mkdir(parents=True)
        (idx / "AI" / "Neural_Networks" / "information.md").write_text(
            "Neural networks are computational models inspired by the brain.\n"
            "They consist of layers of neurons that process information.",
            encoding="utf-8",
        )
        (idx / "AI" / "Transformers").mkdir(parents=True)
        (idx / "AI" / "Transformers" / "information.md").write_text(
            "Transformers use self-attention mechanisms for sequence processing.\n"
            "They are the foundation of modern LLMs like GPT and Claude.",
            encoding="utf-8",
        )
        (idx / "Economics").mkdir(parents=True)
        (idx / "Economics" / "information.md").write_text(
            "Supply and demand drive market prices in capitalist economies.",
            encoding="utf-8",
        )
        
        searcher = IndexSearch(cfg)
        
        # Search for neural
        results = searcher.search("neural networks brain")
        assert len(results) > 0
        assert "Neural_Networks" in results[0]["path"]
        
        # Search for transformers
        results = searcher.search("transformers attention LLMs")
        assert len(results) > 0
        assert "Transformers" in results[0]["path"]
        
        # Formatted output
        formatted = searcher.search_formatted("neural networks")
        assert "Indexed Results" in formatted
        
        # No results
        empty = searcher.search("quantum physics entanglement")
        assert len(empty) == 0
        
        print("[PASS] IndexSearch search/search_formatted")

if __name__ == "__main__":
    test_config()
    test_schemas()
    test_scratch_pad()
    test_rolling_summary()
    test_experiences()
    test_index_search()
    print("\n[OK] ALL PHASE 1A TESTS PASSED")
