"""File I/O utilities: atomic writes, encoding detection."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path


def detect_encoding(file_path: str) -> str:
    """Detect file encoding with fallback chain: UTF-8 -> chardet -> latin-1."""
    raw = Path(file_path).read_bytes()

    # Try UTF-8 first
    try:
        raw.decode("utf-8")
        return "utf-8"
    except UnicodeDecodeError:
        pass

    # Try chardet
    try:
        import chardet
        result = chardet.detect(raw)
        if result["encoding"] and result["confidence"] and result["confidence"] > 0.5:
            # Verify it actually works
            raw.decode(result["encoding"])
            return result["encoding"]
    except (ImportError, UnicodeDecodeError, LookupError):
        pass

    # Fallback to latin-1 (never fails for single-byte data)
    return "latin-1"


def read_text_file(file_path: str) -> str:
    """Read a text file with automatic encoding detection."""
    encoding = detect_encoding(file_path)
    return Path(file_path).read_text(encoding=encoding)


def atomic_write(file_path: str, content: str) -> None:
    """Write content to a file atomically using temp file + os.replace()."""
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(
        dir=str(path.parent),
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, str(path))
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
