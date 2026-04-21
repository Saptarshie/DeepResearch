"""MCP tool registry — builds a simple callable dict for internal use.
FastMCP server startup is optional; tools are always available as direct callables.
"""
from __future__ import annotations
from omega_researcher.config import Config
from omega_researcher.mcp.tools.code_executor import CodeExecutor
from omega_researcher.mcp.tools.data_tools import DataTools
from omega_researcher.mcp.tools.search_tools import SearchTools
from omega_researcher.mcp.tools.file_tools import FileTools
from omega_researcher.mcp.tools.skill_tools import SkillTools


def build_tool_registry(
    config: Config,
    llm,
    index_manager,
    skill_loader,
    scratch_pad,
    rolling_summary,
) -> dict:
    """
    Returns a dict of {tool_name: callable} for internal use by ActorAgent.
    Tools can also be exposed via FastMCP if the optional dependency is available.
    """
    executor = CodeExecutor(config)
    data = DataTools(config)
    search = SearchTools(config, index_manager)
    files = FileTools(config, llm, index_manager)
    skills = SkillTools(config, llm, skill_loader)

    registry = {
        # Code execution
        "execute_python": lambda code, timeout_seconds=30: executor.run(code, timeout_seconds),

        # Data tools
        "data_head": lambda file_path, n=10: data.head(file_path, n),
        "data_summary": lambda file_path: data.summary(file_path),
        "data_schema": lambda file_path: data.schema(file_path),
        "data_query": lambda file_path, pandas_query: data.query(file_path, pandas_query),

        # Search tools
        "searxng_search": lambda query, categories="general", max_results=10: search.searxng_search(query, categories, max_results),
        "search_from_indexes": lambda query: search.search_indexes(query),
        "list_indexed_topics": lambda: search.list_topics(),

        # File ingestion
        "ingest_document": lambda file_path: files.ingest(file_path),
        "ingest_data_file": lambda file_path: files.ingest_data(file_path),

        # Skill tools
        "list_skills": lambda: skills.list_all(),
        "load_skill": lambda skill_name: skills.load(skill_name),
        "create_skill": lambda task_description, what_worked, name="": skills.create(task_description, what_worked, name),

        # Memory tools
        "read_scratch_pad": lambda section="": scratch_pad.read(section or None),
        "write_scratch_pad": lambda section, content: scratch_pad.write(section, content) or f"Written to '{section}'",
        "append_scratch_pad": lambda section, note: scratch_pad.append(section, note) or f"Appended to '{section}'",
        "get_rolling_summary": lambda: rolling_summary.get(),
    }

    # Optionally start FastMCP server
    _try_start_fastmcp(registry, config)

    return registry


def _try_start_fastmcp(registry: dict, config: Config) -> None:
    """Try to expose tools via FastMCP if the package is available."""
    try:
        from mcp.server.fastmcp import FastMCP

        mcp = FastMCP("OmegaResearcher")

        for name, fn in registry.items():
            mcp.tool()(fn)

        print(f"[mcp_server] FastMCP registered {len(registry)} tools")
        # Note: mcp.run() would be called separately to start the server
        # For now we just register — tools are used via registry dict internally

    except ImportError:
        print("[mcp_server] FastMCP not installed — tools available as direct callables only")
    except Exception as e:
        print(f"[mcp_server] FastMCP setup skipped: {e}")
