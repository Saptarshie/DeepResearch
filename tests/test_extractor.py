from __future__ import annotations

from deepresearch.extractor import extract_document
from deepresearch.schemas import Document


def test_extract_document_returns_document_instance() -> None:
    html = "<html><head><title>Test</title></head><body>Hello</body></html>"
    result = extract_document(html, "http://example.com")
    assert isinstance(result, Document)
    assert result.title == "Test"
    assert result.url == "http://example.com"


def test_extract_document_empty_html() -> None:
    result = extract_document("", "http://example.com")
    assert isinstance(result, Document)
    assert result.text == ""
    assert result.url == "http://example.com"


def test_extract_document_no_title() -> None:
    html = "<html><body>Hello</body></html>"
    result = extract_document(html, "http://example.com")
    assert isinstance(result, Document)
    assert result.title == ""
