"""Background JSON/file I/O workers to keep the main thread responsive."""
from __future__ import annotations

import json
import os

from PySide6.QtCore import QThread, Signal

from src.utils.log_config import get_logger

logger = get_logger(__name__)


class JsonWriteWorker(QThread):
    """Write a JSON-serialisable dict to disk atomically on a background thread.

    Uses write-to-temp-then-rename so a crash mid-write cannot corrupt the file.
    """

    finished = Signal()
    failed = Signal(str)

    def __init__(self, path: str, data: dict, parent=None) -> None:
        super().__init__(parent)
        self._path = path
        self._data = data

    def run(self) -> None:
        tmp = self._path + ".tmp"
        try:
            os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(self._data, fh, indent=2, ensure_ascii=False)
            os.replace(tmp, self._path)
            self.finished.emit()
        except (OSError, PermissionError, TypeError) as exc:
            logger.error("JsonWriteWorker failed for %s: %s", self._path, exc)
            # Clean up tmp if it exists
            try:
                if os.path.exists(tmp):
                    os.remove(tmp)
            except OSError:
                pass
            self.failed.emit(str(exc))
