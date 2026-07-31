"""Application logging configuration."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from gpc_dtwin.paths import LOG_DIR, ensure_user_directories

LOG_FILE = LOG_DIR / "gpc-dtwin.log"


def configure_logging() -> Path:
    """Configure a rotating local log and return its path."""
    ensure_user_directories()
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(isinstance(handler, RotatingFileHandler) for handler in root.handlers):
        handler = RotatingFileHandler(
            LOG_FILE, maxBytes=2_000_000, backupCount=4, encoding="utf-8"
        )
        handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
        ))
        root.addHandler(handler)
    logging.captureWarnings(True)
    return LOG_FILE
