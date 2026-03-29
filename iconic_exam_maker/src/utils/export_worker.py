"""Background worker for PDF/DOCX export operations."""
from __future__ import annotations

import traceback
from typing import Any, Callable

from PySide6.QtCore import QThread, Signal

from src.utils.log_config import get_logger

logger = get_logger(__name__)


class ExportWorker(QThread):
    """Run any callable in a background thread and emit result signals.

    Usage::

        worker = ExportWorker(PDFExporter.generate_exam_pdf, questions, path, config=cfg)
        worker.finished.connect(on_done)
        worker.failed.connect(on_error)
        worker.start()
    """

    finished = Signal(object)   # result value returned by fn
    failed = Signal(str)        # human-readable error message
    progress = Signal(int, str) # percent (0-100), status message

    def __init__(
        self,
        fn: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        try:
            result = self._fn(*self._args, **self._kwargs)
            self.finished.emit(result)
        except Exception as exc:  # noqa: BLE001
            tb = traceback.format_exc()
            logger.error("ExportWorker failed: %s\n%s", exc, tb)
            self.failed.emit(str(exc))
