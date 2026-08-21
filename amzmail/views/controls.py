from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QAbstractButton, QComboBox, QLabel, QLineEdit


class ValueBinding(QObject):
    """Small get/set adapter used while preserving existing callback code."""

    changed = Signal(object)

    def __init__(self, widget: Any, value: Any = "") -> None:
        super().__init__(widget)
        self.widget = widget
        if isinstance(widget, QComboBox):
            widget.currentTextChanged.connect(self.changed.emit)
        elif isinstance(widget, QLineEdit):
            widget.textChanged.connect(self.changed.emit)
        elif isinstance(widget, QAbstractButton):
            widget.toggled.connect(self.changed.emit)
        self.set(value)

    def get(self) -> Any:
        if isinstance(self.widget, QComboBox):
            return self.widget.currentText()
        if isinstance(self.widget, QLineEdit):
            return self.widget.text()
        if isinstance(self.widget, QAbstractButton):
            return self.widget.isChecked()
        if isinstance(self.widget, QLabel):
            return self.widget.text()
        return None

    def set(self, value: Any) -> None:
        if isinstance(self.widget, QComboBox):
            text = "" if value is None else str(value)
            index = self.widget.findText(text)
            if index < 0 and text:
                self.widget.addItem(text)
                index = self.widget.findText(text)
            self.widget.setCurrentIndex(max(index, 0))
        elif isinstance(self.widget, QLineEdit):
            self.widget.setText("" if value is None else str(value))
        elif isinstance(self.widget, QAbstractButton):
            self.widget.setChecked(bool(value))
        elif isinstance(self.widget, QLabel):
            self.widget.setText("" if value is None else str(value))
