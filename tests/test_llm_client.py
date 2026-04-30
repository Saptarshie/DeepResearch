from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from deepresearch.llm_client import AnthropicClient, LLMClient, OpenAIClient, extract_and_repair_json


def test_extract_and_repair_json_strips_markdown_fence() -> None:
    raw = '```json\n{"key": "value"}\n```'
    result = extract_and_repair_json(raw)
    assert result == '{"key": "value"}'


def test_extract_and_repair_json_repairs_unescaped_backslashes() -> None:
    raw = r'{"path": "C:\hello\world"}'
    result = extract_and_repair_json(raw)
    parsed = json.loads(result)
    assert parsed["path"] == r"C:\hello\world"


def test_anthropic_client_generate_makes_request() -> None:
    with patch("deepresearch.llm_client.anthropic.Anthropic") as MockAnthropic:
        mock_client = MagicMock()
        mock_stream = [
            MagicMock(type="content_block_delta", delta=MagicMock(text="Hello ")),
            MagicMock(type="content_block_delta", delta=MagicMock(text="world")),
        ]
        mock_client.messages.create.return_value = iter(mock_stream)
        MockAnthropic.return_value = mock_client

        client = AnthropicClient(api_key="test-key", model="claude-test")
        result = client.generate("prompt", "system", max_tokens=100)

        assert result == "Hello world"
        mock_client.messages.create.assert_called_once()
        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-test"
        assert call_kwargs["max_tokens"] == 100
        assert call_kwargs["system"] == "system"


def test_openai_client_generate_makes_request() -> None:
    with patch("deepresearch.llm_client.openai.OpenAI") as MockOpenAI:
        mock_client = MagicMock()
        mock_chunk1 = MagicMock()
        mock_chunk1.choices = [MagicMock(delta=MagicMock(content="Hello "))]
        mock_chunk2 = MagicMock()
        mock_chunk2.choices = [MagicMock(delta=MagicMock(content="world"))]
        mock_client.chat.completions.create.return_value = iter([mock_chunk1, mock_chunk2])
        MockOpenAI.return_value = mock_client

        client = OpenAIClient(api_key="test-key", model="gpt-test")
        result = client.generate("prompt", "system", max_tokens=100)

        assert result == "Hello world"
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-test"
        assert call_kwargs["max_tokens"] == 100


def test_llm_client_uses_default_provider() -> None:
    with patch("deepresearch.llm_client.anthropic.Anthropic") as MockAnthropic:
        mock_client = MagicMock()
        mock_client.messages.create.return_value = iter([])
        MockAnthropic.return_value = mock_client

        config = MagicMock()
        config.anthropic_api_key = "ak"
        config.anthropic_model = "claude-test"
        config.anthropic_base_url = None
        config.openai_api_key = ""
        config.openai_model = "gpt-test"
        config.openai_base_url = "https://api.openai.com/v1"
        config.default_provider = "anthropic"
        config.max_tokens = 1000

        llm = LLMClient(config)
        llm.generate("hello")

        mock_client.messages.create.assert_called_once()


def test_llm_client_raises_when_provider_unavailable() -> None:
    config = MagicMock()
    config.anthropic_api_key = ""
    config.openai_api_key = ""
    config.default_provider = "anthropic"
    config.max_tokens = 1000

    llm = LLMClient(config)
    try:
        llm.generate("hello")
        assert False, "Expected RuntimeError"
    except RuntimeError as e:
        assert "anthropic" in str(e).lower()


def test_llm_client_allows_explicit_provider_override() -> None:
    with patch("deepresearch.llm_client.openai.OpenAI") as MockOpenAI:
        mock_client = MagicMock()
        mock_chunk = MagicMock()
        mock_chunk.choices = [MagicMock(delta=MagicMock(content="ok"))]
        mock_client.chat.completions.create.return_value = iter([mock_chunk])
        MockOpenAI.return_value = mock_client

        config = MagicMock()
        config.anthropic_api_key = ""
        config.anthropic_model = "claude-test"
        config.anthropic_base_url = None
        config.openai_api_key = "ok"
        config.openai_model = "gpt-test"
        config.openai_base_url = "https://api.openai.com/v1"
        config.default_provider = "anthropic"
        config.max_tokens = 1000

        llm = LLMClient(config)
        result = llm.generate("hello", provider="openai")
        assert result == "ok"
