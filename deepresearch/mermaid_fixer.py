# deepresearch/mermaid_fixer.py
"""Post-process Mermaid code blocks to fix common LLM output errors."""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# Characters that MUST be inside quoted labels in Mermaid
_SPECIAL_CHARS = re.compile(r'[\(\)\{\}\#\$\%\&\+\<\>\?\!\:\;\=\@\[\]\/\\~\*]')

# Matches a mermaid code block
_MERMAID_BLOCK = re.compile(
    r'```mermaid\n(.*?)```',
    re.DOTALL,
)

# Node patterns per shape type (process double-braces first to avoid partial matches).
# The inner group allows one level of nesting so labels like {foo {bar}} are
# captured in full.
_DOUBLE_BRACE_PATTERN = re.compile(
    r'([A-Za-z0-9_]+)\{\{((?:[^{}]|\{[^}]*\})*)\}\}'
)
_BRACKET_PATTERN = re.compile(
    r'([A-Za-z0-9_]+)\[((?:[^\[\]]|\[[^\]]*\])*)\]'
)
_BRACE_PATTERN = re.compile(
    r'([A-Za-z0-9_]+)\{((?:[^{}]|\{[^}]*\})*)\}'
)
_PAREN_PATTERN = re.compile(
    r'([A-Za-z0-9_]+)\(((?:[^()]|\([^)]*\))*)\)'
)


def _quote_label(label: str) -> str:
    """Quote a label if it contains Mermaid-special characters."""
    # Already quoted
    if label.startswith('"') and label.endswith('"'):
        return label
    # Contains special chars that break Mermaid → quote it
    if _SPECIAL_CHARS.search(label):
        return f'"{label}"'
    return label


def _replace_double_brace(m: re.Match) -> str:
    return f'{m.group(1)}{{{{_quote_label(m.group(2))}}}}'


def _replace_bracket(m: re.Match) -> str:
    return f'{m.group(1)}[{_quote_label(m.group(2))}]'


def _replace_brace(m: re.Match) -> str:
    return f'{m.group(1)}{{{_quote_label(m.group(2))}}}'


def _replace_paren(m: re.Match) -> str:
    return f'{m.group(1)}({_quote_label(m.group(2))})'


def fix_mermaid_block(block: str) -> str:
    """Fix a single Mermaid code block.

    Returns the fixed block, or the original if no fixes were needed.
    """
    # Use split('\n') instead of splitlines() to preserve trailing newlines
    lines = block.split('\n')
    fixed_lines: list[str] = []
    changed = False

    for line in lines:
        stripped = line.strip()
        # Skip comments, subgraph headers, style lines, empty lines
        if (
            not stripped
            or stripped.startswith('%%')
            or stripped.startswith('subgraph')
            or stripped.startswith('end')
            or stripped.startswith('style ')
            or stripped.startswith('classDef ')
            or stripped.startswith('class ')
        ):
            fixed_lines.append(line)
            continue

        # Fix unquoted special chars in node labels (double-brace first!)
        new_line = _DOUBLE_BRACE_PATTERN.sub(_replace_double_brace, line)
        new_line = _BRACKET_PATTERN.sub(_replace_bracket, new_line)
        new_line = _BRACE_PATTERN.sub(_replace_brace, new_line)
        new_line = _PAREN_PATTERN.sub(_replace_paren, new_line)

        if new_line != line:
            changed = True
        fixed_lines.append(new_line)

    if changed:
        logger.info("Fixed malformed Mermaid block (%d chars)", len(block))
    return '\n'.join(fixed_lines)


def fix_all_mermaid(text: str) -> str:
    """Find and fix all Mermaid blocks in markdown text."""
    def _fix_block(m: re.Match) -> str:
        original = m.group(1)
        fixed = fix_mermaid_block(original)
        return f'```mermaid\n{fixed}```'

    return _MERMAID_BLOCK.sub(_fix_block, text)