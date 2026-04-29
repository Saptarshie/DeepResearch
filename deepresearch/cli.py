#!/usr/bin/env python
"""CLI for DeepSearch Research System."""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys

from deepresearch import deep_search


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def main():
    parser = argparse.ArgumentParser(description="DeepSearch Research System")
    parser.add_argument("topic", nargs="?", help="Research topic")
    parser.add_argument("--max-docs", type=int, default=None, help="Maximum documents to fetch")
    parser.add_argument("--output", "-o", type=str, default=None, help="Output file path")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")
    args = parser.parse_args()

    setup_logging(args.verbose)

    topic = args.topic
    if not topic and not sys.stdin.isatty():
        topic = sys.stdin.read().strip()

    if not topic:
        parser.print_help()
        sys.exit(1)

    config = {}
    if args.max_docs is not None:
        config["max_docs"] = args.max_docs

    print(f"Researching: {topic}", file=sys.stderr)
    print("-" * 50, file=sys.stderr)
    report = asyncio.run(deep_search(topic, config=config))
    print(report)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(report)


if __name__ == "__main__":
    main()
