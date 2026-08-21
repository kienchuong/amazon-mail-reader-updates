from __future__ import annotations

import re
from typing import Any, Callable, Iterable

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtGui import QColor, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)


ELLIPSIS = "…"


def shorten(value: Any, limit: int = 25) -> str:
    text = "" if value is None else str(value)
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + ELLIPSIS


def _natural_key(value: Any) -> tuple:
    text = "" if value is None else str(value)
    return tuple(int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", text))


class TableModel(QAbstractTableModel):
    def __init__(
        self,
        columns: Iterable[str],
        headings: dict[str, str],
        *,
        center_columns: Iterable[str] = (),
        right_columns: Iterable[str] = (),
        truncate_columns: Iterable[str] = (),
        status_columns: Iterable[str] = (),
    ) -> None:
        super().__init__()
        self.columns = tuple(columns)
        self.headings = headings
        self.center_columns = set(center_columns)
        self.right_columns = set(right_columns)
        self.truncate_columns = set(truncate_columns)
        self.status_columns = set(status_columns)
        self.rows: list[dict[str, Any]] = []

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.columns)

    def data(self, index: QModelIndex, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or not (0 <= index.row() < len(self.rows)):
            return None
        column = self.columns[index.column()]
        full = self.rows[index.row()]["values"][index.column()]
        display = shorten(full) if column in self.truncate_columns else full
        if role == Qt.ItemDataRole.DisplayRole:
            return display
        if role == Qt.ItemDataRole.ToolTipRole and display != full:
            return full
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if column in self.right_columns:
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            if column in self.center_columns:
                return int(Qt.AlignmentFlag.AlignCenter)
            return int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        if column in self.status_columns:
            colors = self._status_colors(full)
            if colors and role == Qt.ItemDataRole.BackgroundRole:
                return QColor(colors[0])
            if colors and role == Qt.ItemDataRole.ForegroundRole:
                return QColor(colors[1])
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role=Qt.ItemDataRole.DisplayRole):
        if orientation != Qt.Orientation.Horizontal or not (0 <= section < len(self.columns)):
            return super().headerData(section, orientation, role)
        column = self.columns[section]
        if role == Qt.ItemDataRole.DisplayRole:
            return self.headings[column]
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if column in self.right_columns:
                return int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            return int(Qt.AlignmentFlag.AlignCenter)
        return None

    def flags(self, index: QModelIndex):
        del index
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable

    def sort(self, column: int, order: Qt.SortOrder = Qt.SortOrder.AscendingOrder) -> None:
        if not (0 <= column < len(self.columns)):
            return
        self.layoutAboutToBeChanged.emit()
        self.rows.sort(
            key=lambda row: _natural_key(row["values"][column]),
            reverse=order == Qt.SortOrder.DescendingOrder,
        )
        self.layoutChanged.emit()

    def clear(self) -> None:
        self.beginResetModel()
        self.rows.clear()
        self.endResetModel()

    def append(self, item_id: str, values: Iterable[Any]) -> None:
        row = self.rowCount()
        self.beginInsertRows(QModelIndex(), row, row)
        self.rows.append({
            "id": str(item_id),
            "values": ["" if value is None else str(value) for value in values],
        })
        self.endInsertRows()

    def key_at(self, row: int) -> str | None:
        return self.rows[row]["id"] if 0 <= row < len(self.rows) else None

    def row_for_key(self, item_id: str) -> int:
        key = str(item_id)
        return next((index for index, row in enumerate(self.rows) if row["id"] == key), -1)

    @staticmethod
    def _status_colors(value: str) -> tuple[str, str] | None:
        dark = QApplication.palette().color(QApplication.palette().ColorRole.Window).lightness() < 128
        palette = {
            "payment": (("#dff3e4", "#175c2c"), ("#183d27", "#8fe3a6")),
            "security": (("#fde7e9", "#9c1c28"), ("#4a2328", "#ff9aa5")),
            "high": (("#fde7e9", "#9c1c28"), ("#4a2328", "#ff9aa5")),
            "amazon": (("#e3effd", "#175c9c"), ("#193753", "#8ec5ff")),
            "amazon account": (("#e3effd", "#175c9c"), ("#193753", "#8ec5ff")),
            "normal": (("#edf0f3", "#4b5563"), ("#343940", "#d5dae0")),
        }
        pair = palette.get(value.strip().casefold())
        return pair[1 if dark else 0] if pair else None


class DataTableView(QTableView):
    def keyPressEvent(self, event) -> None:
        if event.matches(QKeySequence.StandardKey.Copy):
            indexes = sorted(self.selectedIndexes(), key=lambda item: (item.row(), item.column()))
            if indexes:
                rows: dict[int, list[str]] = {}
                for index in indexes:
                    rows.setdefault(index.row(), []).append(str(index.data() or ""))
                QApplication.clipboard().setText("\n".join("\t".join(values) for values in rows.values()))
            return
        super().keyPressEvent(event)


class FluentDataTable(QFrame):
    """Read-only Qt model/view table exposing the small API used by the app."""

    def __init__(
        self,
        parent: QWidget,
        columns: Iterable[str],
        headings: dict[str, str],
        widths: dict[str, int],
        *,
        center_columns: Iterable[str] = (),
        right_columns: Iterable[str] = (),
        truncate_columns: Iterable[str] = (),
        status_columns: Iterable[str] = (),
    ) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.columns = tuple(columns)
        self.default_widths = dict(widths)
        self._counter = 0
        self._callbacks: list[Callable] = []
        self.model = TableModel(
            self.columns,
            headings,
            center_columns=center_columns,
            right_columns=right_columns,
            truncate_columns=truncate_columns,
            status_columns=status_columns,
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)
        tools = QHBoxLayout()
        hint = QLabel("Kéo vạch cột để đổi độ rộng • nhấp đúp để tự căn")
        hint.setObjectName("muted")
        reset = QPushButton("Đặt lại cột")
        reset.setObjectName("secondaryButton")
        reset.clicked.connect(self.reset_columns)
        tools.addWidget(hint)
        tools.addStretch(1)
        tools.addWidget(reset)
        layout.addLayout(tools)

        self.table = DataTableView(self)
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(False)
        self.table.setSortingEnabled(True)
        self.table.verticalHeader().hide()
        self.table.verticalHeader().setDefaultSectionSize(34)
        self.table.horizontalHeader().setMinimumSectionSize(48)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().sectionDoubleClicked.connect(self.table.resizeColumnToContents)
        self.table.selectionModel().selectionChanged.connect(self._selection_changed)
        layout.addWidget(self.table, 1)
        self.reset_columns()

    def bind(self, sequence=None, func=None, add=None):
        del add
        if sequence == "<<TreeviewSelect>>" and func is not None:
            self._callbacks.append(func)

    def _selection_changed(self, *_args) -> None:
        for callback in tuple(self._callbacks):
            callback(None)

    def selection(self) -> list[str]:
        rows = self.table.selectionModel().selectedRows()
        key = self.model.key_at(rows[0].row()) if rows else None
        return [key] if key is not None else []

    def selection_set(self, *items: str) -> None:
        if not items:
            return
        row = self.model.row_for_key(str(items[0]))
        if row >= 0:
            self.table.selectRow(row)

    def focus(self, item: str | None = None):
        if item is not None:
            self.selection_set(item)
        self.table.setFocus()
        return item

    def get_children(self) -> list[str]:
        return [row["id"] for row in self.model.rows]

    def delete(self, *items: str) -> None:
        del items
        self.model.clear()

    def insert(self, parent="", index="end", iid=None, values=()) -> str:
        del parent, index
        if iid is None:
            self._counter += 1
            iid = f"row-{self._counter}"
        self.model.append(str(iid), values)
        return str(iid)

    def reset_columns(self) -> None:
        for index, column in enumerate(self.columns):
            self.table.setColumnWidth(index, self.default_widths[column])

    def fit_columns(self) -> None:
        for index, column in enumerate(self.columns):
            self.table.resizeColumnToContents(index)
            width = max(self.default_widths.get(column, 64), self.table.columnWidth(index))
            self.table.setColumnWidth(index, min(width, 360))

    def apply_appearance(self) -> None:
        if not self.model.rowCount() or not self.model.columnCount():
            return
        self.model.dataChanged.emit(
            self.model.index(0, 0),
            self.model.index(self.model.rowCount() - 1, self.model.columnCount() - 1),
        )


class FluentSplitPane(QSplitter):
    def __init__(self, parent: QWidget, ratio: float = 0.72) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.left = QFrame(self)
        self.left.setObjectName("card")
        self.right = QFrame(self)
        self.right.setObjectName("card")
        self.addWidget(self.left)
        self.addWidget(self.right)
        self.setChildrenCollapsible(False)
        self.setHandleWidth(6)
        self.setStretchFactor(0, max(1, round(ratio * 100)))
        self.setStretchFactor(1, max(1, 100 - round(ratio * 100)))
        self.setSizes([720, 280])
