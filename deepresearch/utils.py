from __future__ import annotations

import re


def sanitize_dirname(name: str) -> str:
    """Replace non-alphanumeric characters with underscores."""
    return re.sub(r"[^a-zA-Z0-9_]+", "_", name).strip("_")
