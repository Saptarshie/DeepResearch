from __future__ import annotations

import json

from deepresearch.llm_client import extract_and_repair_json


def test_extract_and_repair_json_strips_markdown_fence() -> None:
    raw = "```json\n{\"key\": \"value\"}\n```"
    result = extract_and_repair_json(raw)
    assert result == '{"key": "value"}'


def test_extract_and_repair_json_repairs_unescaped_backslashes() -> None:
    raw = r'{"path": "C:\hello\world"}'
    result = extract_and_repair_json(raw)
    parsed = json.loads(result)
    assert parsed["path"] == r"C:\hello\world"
