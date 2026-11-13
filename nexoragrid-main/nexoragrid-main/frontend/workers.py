"""Small QThread wrapper for model inference and simulations."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QThread, Signal


class FunctionWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, function: Callable, *args, parent=None, **kwargs) -> None:
        super().__init__(parent)
        self.function = function
        self.args = args
        self.kwargs = kwargs

    def run(self) -> None:
        try:
            self.succeeded.emit(self.function(*self.args, **self.kwargs))
        except Exception as exc:  # surfaced in the page's status area
            self.failed.emit(str(exc))
