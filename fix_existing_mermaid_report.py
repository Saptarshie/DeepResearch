#!/usr/bin/env python
"""Fix Mermaid blocks in an existing markdown report.

Usage:
    python fix_existing_mermaid_report.py ./outputs/Billionaire_Guide.md
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from deepresearch.mermaid_fixer import fix_all_mermaid


def fix_report(path: Path) -> None:
    if not path.exists():
        print(f"Error: file not found: {path}", file=sys.stderr)
        sys.exit(1)

    original = path.read_text(encoding="utf-8")
    fixed = fix_all_mermaid(original)

    if fixed == original:
        print(f"No malformed Mermaid blocks found in: {path}")
        return

    path.write_text(fixed, encoding="utf-8")
    print(f"Fixed Mermaid blocks and saved: {path}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Fix malformed Mermaid blocks in an existing markdown report."
    )
    parser.add_argument(
        "file",
        type=Path,
        help="Path to the markdown file to fix (e.g., ./outputs/Billionaire_Guide.md)",
    )
    args = parser.parse_args(argv)
    fix_report(args.file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
