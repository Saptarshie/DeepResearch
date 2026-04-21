#!/usr/bin/env python
"""CLI for OmegaResearcher."""
from __future__ import annotations
import argparse
import asyncio
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        prog="omega_researcher",
        description="OmegaResearcher — Autonomous Research Intelligence System",
    )
    parser.add_argument("query", nargs="?", help="Research topic or question")
    parser.add_argument(
        "--files", "-f", nargs="+", metavar="FILE",
        help="PDF, DOCX, PPTX, HTML, CSV, or Excel files to ingest",
    )
    parser.add_argument(
        "--max-docs", type=int, default=None,
        help="Maximum web documents to crawl (default: config value)",
    )
    parser.add_argument(
        "--no-subagents", action="store_true",
        help="Disable recursive sub-agent spawning",
    )
    parser.add_argument(
        "--depth-limit", type=int, default=None,
        help="Override SPAWNING_DEPTH_LIMIT",
    )
    parser.add_argument(
        "--output", "-o", default="report-content.md",
        help="Output file path (default: report-content.md)",
    )

    args = parser.parse_args()

    # Query from arg or stdin
    query = args.query
    if not query:
        if not sys.stdin.isatty():
            query = sys.stdin.read().strip()
        if not query:
            parser.error("Please provide a research query.")

    # Build config with overrides
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from omega_researcher.config import Config
    from omega_researcher.orchestrator import Orchestrator

    config = Config()
    if args.max_docs is not None:
        config.max_docs = args.max_docs
    if args.depth_limit is not None:
        config.SPAWNING_DEPTH_LIMIT = args.depth_limit
    if args.no_subagents:
        config.SPAWNING_DEPTH_LIMIT = 0

    print(f"[omega_researcher] Query: {query}", file=sys.stderr)
    print(f"[omega_researcher] Files: {args.files or []}", file=sys.stderr)
    print("-" * 60, file=sys.stderr)

    async def run():
        orch = Orchestrator(config=config)
        state = await orch.run(
            query=query,
            file_paths=args.files or [],
        )
        # Read output file
        output = Path(args.output)
        if output.exists():
            report = output.read_text(encoding="utf-8")
        else:
            report = state.rolling_summary or "[No report generated]"
        return report

    report = asyncio.run(run())
    print(report)


if __name__ == "__main__":
    main()
