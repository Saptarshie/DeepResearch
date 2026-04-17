from __future__ import annotations
import json
from trafilatura import extract, bare_extraction
def extract_document(html: str, url: str) -> dict:
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
    meta: dict = {}
    if isinstance(meta_raw, dict):
        meta = meta_raw
    elif isinstance(meta_raw, str):
        try:
            meta = json.loads(meta_raw)
        except (json.JSONDecodeError, TypeError):
            meta = {}
    return {
        "title": meta.get("title", "") if isinstance(meta, dict) else "",
        "text": text,
        "author": meta.get("author", "") if isinstance(meta, dict) else "",
        "published_at": meta.get("date", "") if isinstance(meta, dict) else "",
        "language": meta.get("language", "unknown")
        if isinstance(meta, dict)
        else "unknown",
        "metadata": meta if isinstance(meta, dict) else {},
    }