"""Filename sanitization and URL validation utilities."""

from __future__ import annotations

import re
from urllib.parse import urlparse


def sanitize_filename(name: str, max_length: int = 200) -> str:
    """Sanitize a string for use as a filename.

    Replaces unsafe characters, collapses whitespace, and truncates.
    """
    # Remove or replace unsafe characters
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name)
    # Collapse whitespace and underscores
    name = re.sub(r"[\s_]+", "_", name).strip("_. ")
    # Truncate
    if len(name) > max_length:
        name = name[:max_length].rstrip("_. ")
    return name or "unnamed"


def is_url(source: str) -> bool:
    """Check if a string looks like a URL."""
    try:
        parsed = urlparse(source)
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False
