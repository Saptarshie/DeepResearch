#!/usr/bin/env python
"""CLI for DeepSearch Research System."""

from __future__ import annotations
import asyncio
import sys
from deepresearch import deep_search


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m deepresearch.cli <research_topic>")
        print("       echo 'your topic' | python -m deepresearch.cli")
        sys.exit(1)

    topic = sys.argv[1] if len(sys.argv) > 1 else sys.stdin.read().strip()
    if not topic:
        print("Error: no topic provided")
        sys.exit(1)

    print(f"Researching: {topic}", file=sys.stderr)
    print("-" * 50, file=sys.stderr)
    report = asyncio.run(deep_search(topic))
    print(report)


if __name__ == "__main__":
    main()
