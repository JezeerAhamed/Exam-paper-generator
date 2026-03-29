"""Platform-agnostic utilities for Iconic Exam Maker."""
from __future__ import annotations

import os
import subprocess
import sys

from src.utils.log_config import get_logger

logger = get_logger(__name__)


def open_path(path: str) -> bool:
    """Open a file or folder with the OS default application.

    Works on Windows, macOS, and Linux.

    Returns:
        True if the command was launched successfully, False otherwise.
    """
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
        return True
    except (OSError, FileNotFoundError, AttributeError) as exc:
        logger.warning("Could not open %s: %s", path, exc)
        return False


def get_system_font_dir() -> str:
    """Return the OS default font directory."""
    if sys.platform == "win32":
        return os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    if sys.platform == "darwin":
        return "/Library/Fonts"
    return "/usr/share/fonts"
