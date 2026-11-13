"""Page base class with safe background-task handling."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from .workers import FunctionWorker
from .styles import PALETTE, set_label_style


class BasePage(QWidget):
    task_succeeded = Signal(object, object)
    task_failed = Signal(object, str)

    def __init__(self, service, parent=None) -> None:
        super().__init__(parent)
        self.service = service
        self._workers: set[FunctionWorker] = set()
        self._callbacks: dict[FunctionWorker, tuple[Callable, Callable | None, object]] = {}
        self.task_succeeded.connect(self._handle_success, Qt.ConnectionType.QueuedConnection)
        self.task_failed.connect(self._handle_failure, Qt.ConnectionType.QueuedConnection)
        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(24, 18, 24, 22)
        self.root_layout.setSpacing(15)
        self.status_label = QLabel("")
        set_label_style(self.status_label, color=PALETTE["muted"], size=9)
        self.status_label.setWordWrap(True)

    def launch(
        self,
        function: Callable,
        on_success: Callable,
        *,
        on_error: Callable | None = None,
        busy_widget=None,
        busy_text: str = "Working…",
    ) -> None:
        if busy_widget:
            busy_widget.setEnabled(False)
            if hasattr(busy_widget, "text"):
                busy_widget.setProperty("busy_original_text", busy_widget.text())
                busy_widget.setText(busy_text)
        worker = FunctionWorker(function, parent=self)
        self._workers.add(worker)
        self._callbacks[worker] = (on_success, on_error, busy_widget)
        worker.succeeded.connect(lambda result, current=worker: self.task_succeeded.emit(current, result))
        worker.failed.connect(lambda message, current=worker: self.task_failed.emit(current, message))
        worker.finished.connect(lambda current=worker: self._workers.discard(current))
        worker.start()

    @Slot(object, object)
    def _handle_success(self, worker: FunctionWorker, result: object) -> None:
        callback = self._callbacks.pop(worker, None)
        if callback is None:
            return
        on_success, _, busy_widget = callback
        self._restore_busy_widget(busy_widget)
        self.status_label.setText("")
        set_label_style(self.status_label, color=PALETTE["muted"], size=9)
        on_success(result)

    @Slot(object, str)
    def _handle_failure(self, worker: FunctionWorker, message: str) -> None:
        callback = self._callbacks.pop(worker, None)
        if callback is None:
            return
        _, on_error, busy_widget = callback
        self._restore_busy_widget(busy_widget)
        self.status_label.setText(f"Could not complete: {message}")
        set_label_style(self.status_label, color=PALETTE["red"], size=9)
        if on_error:
            on_error(message)

    @staticmethod
    def _restore_busy_widget(widget) -> None:
        if widget:
            widget.setEnabled(True)
            original = widget.property("busy_original_text")
            if original:
                widget.setText(original)

    def refresh(self) -> None:
        """Pages override this when they expose a refresh action."""

    def closeEvent(self, event) -> None:
        for worker in tuple(self._workers):
            worker.requestInterruption()
            worker.wait(1200)
        super().closeEvent(event)
