from __future__ import annotations
import json
from lxml import html as lh
from trafilatura import extract, bare_extraction
from deepresearch.schemas import Document


def _extract_title_from_html(html: str) -> str:
    try:
        tree = lh.fromstring(html)
        title = tree.findtext(".//title")
        return title.strip() if title else ""
    except Exception:
        return ""


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
    meta: dict = {}
    if isinstance(meta_raw, dict):
        meta = meta_raw
    elif hasattr(meta_raw, "as_dict"):
        meta = meta_raw.as_dict()
    elif isinstance(meta_raw, str):
        try:
            meta = json.loads(meta_raw)
        except (json.JSONDecodeError, TypeError):
            meta = {}

    title = meta.get("title", "") if isinstance(meta, dict) else ""
    if not title:
        title = _extract_title_from_html(html)

    return Document(
        url=url,
        canonical_url=url.split("#")[0],
        title=title,
        text=text,
        author=meta.get("author", "") if isinstance(meta, dict) else "",
        published_at=meta.get("date", "") if isinstance(meta, dict) else "",
        language=meta.get("language", "unknown")
        if isinstance(meta, dict)
        else "unknown",
        metadata=meta if isinstance(meta, dict) else {},
    )