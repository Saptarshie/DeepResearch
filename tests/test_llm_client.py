from __future__ import annotations
import pytest
from deepresearch.llm_client import fix_json_escapes


def test_fix_json_escapes_strips_markdown_fence() -> None:
    raw = "```json\n{\"key\": \"value\"}\n```"
    result = fix_json_escapes(raw)
    assert result == '{"key": "value"}'


def test_fix_json_escapes_repairs_unescaped_backslashes() -> None:
    raw = '{"path": "C:\\Users\\name"}'
    result = fix_json_escapes(raw)
    assert "path" in result
