from __future__ import annotations

import json
from typing import Any

from lxml import html as lh  # type: ignore[import-untyped]
from trafilatura import bare_extraction, extract

from deepresearch.schemas import Document


def _extract_title_from_html(html: str) -> str:
    try:
        tree = lh.fromstring(html)
        title = tree.findtext(".//title")
        return title.strip() if title else ""
    except Exception:
        return ""


def _safe_meta_get(meta: dict[str, Any] | None, key: str, default: str = "") -> str:
    if isinstance(meta, dict):
        value = meta.get(key, default)
        if value is None:
            return default
        if isinstance(value, str):
            return value
        return str(value)
    return default


def extract_document(html: str, url: str) -> Document:
    text = (
        extract(
            html,
            url=url,
            include_comments=False,
            include_tables=True,
            favor_precision=True,
        )
        or ""
    )
    meta_raw = bare_extraction(html, url=url)
    meta: dict[str, Any] = {}
    if isinstance(meta_raw, dict):
        meta = meta_raw
    elif meta_raw is not None and hasattr(meta_raw, "as_dict"):
        meta = meta_raw.as_dict()
    elif isinstance(meta_raw, str):
        try:
            meta = json.loads(meta_raw)
        except (json.JSONDecodeError, TypeError):
            meta = {}

    title = _safe_meta_get(meta, "title")
    if not title:
        title = _extract_title_from_html(html)

    return Document(
        url=url,
        canonical_url=url.split("#")[0],
        title=title,
        text=text,
        author=_safe_meta_get(meta, "author"),
        published_at=_safe_meta_get(meta, "date"),
        language=_safe_meta_get(meta, "language", "unknown"),
        metadata=meta if isinstance(meta, dict) else {},
    )
