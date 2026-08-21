from __future__ import annotations

from PySide6.QtCore import QObject, Signal


class WorkerEventBridge(QObject):
    """Thread-safe bridge matching the old queue ``put`` call surface."""

    event = Signal(str, object)

    def put(self, item: tuple[str, object]) -> None:
        kind, payload = item
        self.event.emit(kind, payload)
