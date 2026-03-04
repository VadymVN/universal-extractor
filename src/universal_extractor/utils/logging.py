"""Structured logging setup."""

from __future__ import annotations

import logging
import sys


def setup_logging(level: str = "INFO") -> None:
    """Configure logging with a consistent format."""
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    root = logging.getLogger("universal_extractor")
    root.setLevel(numeric_level)
    # Avoid duplicate handlers on repeated calls
    root.handlers.clear()
    root.addHandler(handler)
