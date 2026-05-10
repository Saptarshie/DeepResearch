from __future__ import annotations

import pytest

from deepresearch.mermaid_fixer import (
    _quote_label,
    fix_all_mermaid,
    fix_mermaid_block,
)


# ---------------------------------------------------------------------------
# _quote_label
# ---------------------------------------------------------------------------

def test_quote_label_plain() -> None:
    assert _quote_label("Hello") == "Hello"


def test_quote_label_dollar() -> None:
    assert _quote_label("Cost $100") == '"Cost $100"'


def test_quote_label_parens() -> None:
    assert _quote_label("foo()") == '"foo()"'


def test_quote_label_plus() -> None:
    assert _quote_label("A + B") == '"A + B"'
test_quote_label_plus()

def test_quote_label_question() -> None:
    assert _quote_label("What?") == '"What?"'


def test_quote_label_ampersand() -> None:
    assert _quote_label("R&D") == '"R&D"'


def test_quote_label_already_quoted() -> None:
    assert _quote_label('"already quoted"') == '"already quoted"'


def test_quote_label_empty() -> None:
    assert _quote_label("") == ""


# ---------------------------------------------------------------------------
# fix_mermaid_block
# ---------------------------------------------------------------------------

def test_fix_block_no_special_chars() -> None:
    block = "graph TD\n    A[Start] --> B[End]"
    assert fix_mermaid_block(block) == block


def test_fix_block_dollar_sign() -> None:
    block = "graph TD\n    A[Revenue $100M] --> B[Profit]"
    fixed = fix_mermaid_block(block)
    assert 'A["Revenue $100M"]' in fixed


def test_fix_block_parens() -> None:
    block = "graph TD\n    A[init()] --> B[run()]"
    fixed = fix_mermaid_block(block)
    assert 'A["init()"]' in fixed
    assert 'B["run()"]' in fixed


def test_fix_block_plus_and_question() -> None:
    block = "graph TD\n    A[Add +?] --> B[Result]"
    fixed = fix_mermaid_block(block)
    assert 'A["Add +?"]' in fixed


def test_fix_block_curly_braces() -> None:
    block = "graph TD\n    A{foo {bar}}"
    fixed = fix_mermaid_block(block)
    assert 'A{"foo {bar}"}' in fixed


def test_fix_block_ignores_comments() -> None:
    block = "graph TD\n    %% A[Cost $100]\n    B[End]"
    fixed = fix_mermaid_block(block)
    assert "%% A[Cost $100]" in fixed
    assert "B[End]" in fixed


def test_fix_block_ignores_subgraph() -> None:
    block = "graph TD\n    subgraph $foo\n        A[Start]\n    end"
    fixed = fix_mermaid_block(block)
    assert "subgraph $foo" in fixed
    assert "A[Start]" in fixed


def test_fix_block_ignores_style_lines() -> None:
    block = "graph TD\n    style A fill:#f9f\n    A[Start] --> B[End]"
    fixed = fix_mermaid_block(block)
    assert "style A fill:#f9f" in fixed


def test_fix_block_already_quoted_not_requoted() -> None:
    block = 'graph TD\n    A["Cost $100"] --> B[End]'
    fixed = fix_mermaid_block(block)
    assert 'A["Cost $100"]' in fixed
    # B has no special chars, stays bare
    assert "B[End]" in fixed


def test_fix_block_multiple_nodes_on_line() -> None:
    block = "graph TD\n    A[foo()] --> B[bar $1]"
    fixed = fix_mermaid_block(block)
    assert 'A["foo()"]' in fixed
    assert 'B["bar $1"]' in fixed


def test_fix_block_empty_lines_preserved() -> None:
    block = "graph TD\n\n    A[Start]\n\n"
    fixed = fix_mermaid_block(block)
    assert fixed == block


# ---------------------------------------------------------------------------
# fix_all_mermaid
# ---------------------------------------------------------------------------

def test_fix_all_no_blocks() -> None:
    text = "# Hello\n\nNo mermaid here."
    assert fix_all_mermaid(text) == text


def test_fix_all_single_block() -> None:
    text = "# Report\n\n```mermaid\ngraph TD\n    A[Cost $100]\n```\n\nMore text."
    fixed = fix_all_mermaid(text)
    assert 'A["Cost $100"]' in fixed
    assert "```mermaid" in fixed
    assert "More text." in fixed


def test_fix_all_multiple_blocks() -> None:
    text = (
        "# Report\n\n"
        "```mermaid\ngraph TD\n    A[Cost $100]\n```\n\n"
        "Some paragraph.\n\n"
        "```mermaid\ngraph LR\n    B[init()] --> C[done?]\n```"
    )
    fixed = fix_all_mermaid(text)
    assert 'A["Cost $100"]' in fixed
    assert 'B["init()"]' in fixed
    assert 'C["done?"]' in fixed


def test_fix_all_mixed_backticks() -> None:
    # Ensure we only touch ```mermaid blocks, not ```python etc.
    text = (
        "```python\n"
        "x = [1, 2, $3]\n"
        "```\n\n"
        "```mermaid\ngraph TD\n    A[Cost $100]\n```"
    )
    fixed = fix_all_mermaid(text)
    assert "x = [1, 2, $3]" in fixed  # untouched
    assert 'A["Cost $100"]' in fixed


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_fix_block_angle_brackets() -> None:
    block = "graph TD\n    A[if x < 10]"
    fixed = fix_mermaid_block(block)
    assert 'A["if x < 10"]' in fixed


def test_fix_block_exclamation() -> None:
    block = "graph TD\n    A[Error!]"
    fixed = fix_mermaid_block(block)
    assert 'A["Error!"]' in fixed


def test_fix_block_tilde() -> None:
    block = "graph TD\n    B1 --> C[~5 Year Cycle Established]"
    fixed = fix_mermaid_block(block)
    assert 'C["~5 Year Cycle Established"]' in fixed


def test_fix_block_asterisk() -> None:
    block = "graph TD\n    A[foo * bar]"
    fixed = fix_mermaid_block(block)
    assert 'A["foo * bar"]' in fixed