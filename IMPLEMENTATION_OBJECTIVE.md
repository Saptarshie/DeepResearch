Now I have a complete picture of the codebase. Let me design the full architecture and write the implementation plan.Now I have deep context on every part of the system. Let me build the full implementation plan.Now let me create a comprehensive architecture diagram to go with the plan.Every clickable box in the diagram goes deeper into that subsystem. Here's a summary of the full design:

---

## What the plan covers

**The new system is called `omega_researcher/`** — a drop-in replacement for `deepresearch/`, fully backward-compatible with the original `deep_search(query, config={...})` API.

### The 7 major additions and how they integrate:

**1. Docling document ingestion** — `DoclingParser` handles PDF/DOCX/PPTX/HTML via Docling's pipeline (with OCR), exporting to structured markdown, extracting tables as DataFrames, and collecting figure captions. `DataReader` handles CSV/Excel with `head()`, `summary()`, `schema()`, and `query()`. Both produce unified `IngestedDocument` objects that flow directly into the existing indexer.

**2. Formal PAC loop** — `orchestrator.py` runs `PlannerAgent → ActorAgent → CriticAgent` in a cycle. The Critic now returns **per-subquestion coverage scores (0–1)**, not just a yes/no flag. The Actor calls `_decide_next_action()` — an LLM call that picks between `web_search`, `search_indexes`, `execute_code`, `spawn_subagents`, or `done` — before every action.

**3. MCP server** — `mcp/mcp_server.py` uses FastMCP to expose 12 tools: `execute_python`, `data_head/summary/schema/query`, `searxng_search`, `search_from_indexes`, `list_indexed_topics`, `ingest_document`, `ingest_data_file`, `list/load/create_skill`, and scratch pad read/write. The Docker executor runs pandas, numpy, sklearn, scipy, statsmodels in an isolated sandbox.

**4. `search_from_indexes()`** — keyword + sliding-window density ranking over all `INDEXES/**/*.md` files. Lets the actor recall what was already learned without re-fetching. Plugs into the existing `INDEX-AS-YOU-GO` system which now runs **per-document** (not just at the end).

**5. Sub-agent spawner** — `SubagentSpawner` runs up to 5 parallel sub-agents via `asyncio.gather`, each with its own reduced-budget PAC loop. They **share the same `INDEXES/` directory** so knowledge accumulates globally across all agents. Results are deep-merged back into the parent state. `SPAWNING_DEPTH_LIMIT = 3` is enforced in config.

**6. Dynamic skills** — `SkillLoader` scans `SKILLS/*/SKILL.md` on startup, uses an LLM call to select which are relevant for the current task, and injects their content into the Planner and Actor prompts. `SkillCreator` generates new `SKILL.md` files when the actor encounters a novel task type.

**7. MetaAgent + MetaLearn** — runs in a completely fresh `anthropic.Anthropic()` client with no shared context from research agents. Logs every session to `experiences.jsonl` + `experiences.md`. Every 10 experiences it runs `MetaLearn()` — reads failure patterns, calls `SkillCreator.create/update_skill()` to encode learned behaviors for next time.

### Implementation is in 5 phases, ~5–6 weeks total. Phase 1 (PAC + Docling) is the critical path.
