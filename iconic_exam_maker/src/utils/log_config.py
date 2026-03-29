"""Centralised logging configuration for Iconic Exam Maker."""
from __future__ import annotations

import logging
import os
from logging.handlers import RotatingFileHandler

_LOG_DIR = "logs"
_LOG_FILE = os.path.join(_LOG_DIR, "app.log")
_configured = False


def configure_logging(level: int = logging.DEBUG) -> None:
    """Set up root logger with rotating file handler + stream handler.

    Safe to call multiple times — only configures once.
    """
    global _configured
    if _configured:
        return
    _configured = True

    os.makedirs(_LOG_DIR, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    root = logging.getLogger()
    root.setLevel(level)

    # Rotating file — max 5 MB × 3 backups
    fh = RotatingFileHandler(
        _LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    fh.setFormatter(fmt)
    fh.setLevel(logging.DEBUG)
    root.addHandler(fh)

    # Console — INFO and above
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    sh.setLevel(logging.INFO)
    root.addHandler(sh)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger, configuring logging on first call."""
    configure_logging()
    return logging.getLogger(name)
