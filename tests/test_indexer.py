from __future__ import annotations

from unittest.mock import MagicMock

from deepresearch.config import Config
from deepresearch.synthesizer.indexer import Indexer


def test_indexer_batches_documents() -> None:
    cfg = Config(anthropic_api_key="fake", anthropic_model="fake", indexer_batch_size=5)
    llm = MagicMock()
    llm.json.return_value = {
        "updated_topics_hierarchy": {},
        "updated_scratch_pad": "",
        "extracted_information": [],
    }
    indexer = Indexer(llm, cfg)
    docs = [
        {"title": f"Doc {i}", "text": f"Text {i}", "url": f"http://example.com/{i}"}
        for i in range(12)
    ]
    indexer.process_docs(docs, "query")
    # With batch_size=5, expect ceil(12/5) = 3 calls
    assert llm.json.call_count == 3


def test_indexer_preserves_topics_across_batches() -> None:
    cfg = Config(anthropic_api_key="fake", anthropic_model="fake", indexer_batch_size=2)
    llm = MagicMock()
    responses = [
        {
            "updated_topics_hierarchy": {"Topic A": {}},
            "updated_scratch_pad": "scratch 1",
            "extracted_information": [],
        },
        {
            "updated_topics_hierarchy": {"Topic A": {"Sub B": {}}},
            "updated_scratch_pad": "scratch 2",
            "extracted_information": [],
        },
    ]
    llm.json.side_effect = responses
    indexer = Indexer(llm, cfg)
    docs = [
        {"title": "Doc 1", "text": "Text 1", "url": "http://example.com/1"},
        {"title": "Doc 2", "text": "Text 2", "url": "http://example.com/2"},
        {"title": "Doc 3", "text": "Text 3", "url": "http://example.com/3"},
    ]
    result = indexer.process_docs(docs, "query")
    assert "Topic A" in result
    assert "Sub B" in result["Topic A"]
