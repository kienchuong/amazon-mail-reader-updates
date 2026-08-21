from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication, QFileDialog, QMessageBox, QWidget


def _parent(parent: QWidget | None = None) -> QWidget | None:
    return parent or QApplication.activeWindow()


class messagebox:
    @staticmethod
    def showwarning(title: str, text: str, parent: QWidget | None = None) -> None:
        QMessageBox.warning(_parent(parent), title, text)

    @staticmethod
    def showinfo(title: str, text: str, parent: QWidget | None = None) -> None:
        QMessageBox.information(_parent(parent), title, text)

    @staticmethod
    def showerror(title: str, text: str, parent: QWidget | None = None) -> None:
        QMessageBox.critical(_parent(parent), title, text)

    @staticmethod
    def askyesno(title: str, text: str, parent: QWidget | None = None) -> bool:
        answer = QMessageBox.question(
            _parent(parent),
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return answer == QMessageBox.StandardButton.Yes


class filedialog:
    @staticmethod
    def asksaveasfilename(
        *,
        title: str,
        defaultextension: str = "",
        initialfile: str = "",
        initialdir: str = "",
        filetypes=(),
    ) -> str:
        selected_filter = ";;".join(f"{name} ({pattern})" for name, pattern in filetypes)
        path, _ = QFileDialog.getSaveFileName(
            _parent(),
            title,
            str(Path(initialdir) / initialfile),
            selected_filter,
        )
        if path and defaultextension and not path.lower().endswith(defaultextension.lower()):
            path += defaultextension
        return path
