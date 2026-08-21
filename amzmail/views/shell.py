from __future__ import annotations

from PySide6.QtCore import QTimer, Qt
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from amzmail import APP_VERSION
from amzmail.views.controls import ValueBinding
from amzmail.views.data_table import FluentDataTable


class ShellViewMixin:
    def _build_style(self) -> None:
        self._last_appearance: bool | None = None
        self.data_tables: list[FluentDataTable] = []
        self._apply_tree_style(force=True)

    def _build_ui(self) -> None:
        root = QWidget(self)
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = QFrame(root)
        self.sidebar.setObjectName("sidebar")
        self.sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(self.sidebar)
        sidebar_layout.setContentsMargins(10, 20, 10, 18)
        sidebar_layout.setSpacing(6)
        brand = QLabel("Amazon Mail\nReader")
        brand.setObjectName("brand")
        sidebar_layout.addWidget(brand)
        sidebar_layout.addSpacing(18)

        self.nav_buttons: dict[str, QPushButton] = {}
        for key, label in (("inbox", "Inbox"), ("payments", "Payment"), ("accounts", "Accounts"), ("settings", "Cài đặt")):
            button = QPushButton(label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setMinimumHeight(40)
            button.clicked.connect(lambda _checked=False, page=key: self.show_page(page))
            sidebar_layout.addWidget(button)
            self.nav_buttons[key] = button
        sidebar_layout.addStretch(1)
        version = QLabel(f"Phiên bản {APP_VERSION}")
        version.setObjectName("muted")
        read_only = QLabel("Chỉ đọc email")
        read_only.setObjectName("muted")
        sidebar_layout.addWidget(version)
        sidebar_layout.addWidget(read_only)
        root_layout.addWidget(self.sidebar)

        self.main_area = QFrame(root)
        self.main_area.setObjectName("mainArea")
        main_layout = QVBoxLayout(self.main_area)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        header = QFrame(self.main_area)
        header.setObjectName("topBar")
        header.setFixedHeight(64)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(22, 0, 22, 0)
        self.page_title = QLabel("Inbox")
        self.page_title.setObjectName("pageTitle")
        self.page_title_var = ValueBinding(self.page_title, "Inbox")
        header_layout.addWidget(self.page_title)
        header_layout.addStretch(1)
        main_layout.addWidget(header)

        self.content = QStackedWidget(self.main_area)
        self.content.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.pages: dict[str, QWidget] = {}
        for key in ("inbox", "payments", "accounts", "settings"):
            page = QWidget(self.content)
            page.setObjectName("page")
            self.content.addWidget(page)
            self.pages[key] = page

        self.inbox_tab = self.pages["inbox"]
        self.payments_tab = self.pages["payments"]
        self.accounts_tab = self.pages["accounts"]
        self.settings_tab = self.pages["settings"]
        self._build_inbox_view(self.inbox_tab)
        self._build_payments_view(self.payments_tab)
        self._build_accounts_view(self.accounts_tab)
        self._build_settings_view(self.settings_tab)
        main_layout.addWidget(self.content, 1)

        status_frame = QFrame(self.main_area)
        status_frame.setObjectName("statusBar")
        status_layout = QHBoxLayout(status_frame)
        status_layout.setContentsMargins(18, 7, 18, 7)
        self.status_label = QLabel("Sẵn sàng. App chỉ đọc mail, không gửi/xóa/sửa email.")
        self.status_var = ValueBinding(self.status_label, self.status_label.text())
        status_layout.addWidget(self.status_label)
        main_layout.addWidget(status_frame)

        root_layout.addWidget(self.main_area, 1)
        self.show_page("inbox")
        self._appearance_timer = QTimer(self)
        self._appearance_timer.timeout.connect(self._sync_appearance)
        self._appearance_timer.start(1000)

    def _create_tree(
        self,
        parent,
        columns,
        headings,
        widths,
        selectmode="browse",
        center_columns=(),
        right_columns=(),
        truncate_columns=(),
        status_columns=(),
    ):
        del selectmode
        table = FluentDataTable(
            parent,
            columns,
            headings,
            widths,
            center_columns=center_columns,
            right_columns=right_columns,
            truncate_columns=truncate_columns,
            status_columns=status_columns,
        )
        self.data_tables.append(table)
        return table

    def show_page(self, page: str) -> None:
        titles = {"inbox": "Inbox", "payments": "Payment", "accounts": "Accounts", "settings": "Cài đặt"}
        self.content.setCurrentWidget(self.pages[page])
        self.page_title_var.set(titles[page])
        for key, button in self.nav_buttons.items():
            button.setChecked(key == page)

    def _apply_tree_style(self, force: bool = False) -> None:
        dark = QApplication.palette().color(QApplication.palette().ColorRole.Window).lightness() < 128
        if not force and dark == self._last_appearance:
            return
        self._last_appearance = dark
        if dark:
            colors = {
                "bg": "#17191c", "surface": "#202326", "surface2": "#25292e", "text": "#eef1f5",
                "muted": "#aab2bd", "line": "#34383d", "input": "#292d32", "select": "#263f59",
            }
        else:
            colors = {
                "bg": "#f4f6f8", "surface": "#ffffff", "surface2": "#f3f5f8", "text": "#202124",
                "muted": "#667085", "line": "#d7dce2", "input": "#ffffff", "select": "#dce8f5",
            }
        self.setStyleSheet(f"""
            * {{ font-family: "Segoe UI Variable", "Segoe UI"; font-size: 13px; }}
            QMainWindow, QWidget#page, QFrame#mainArea {{ background: {colors['bg']}; color: {colors['text']}; }}
            QFrame#sidebar, QFrame#topBar, QFrame#statusBar {{ background: {colors['surface']}; color: {colors['text']}; }}
            QLabel#brand {{ font-size: 20px; font-weight: 700; }}
            QLabel#pageTitle {{ font-size: 22px; font-weight: 700; }}
            QLabel#sectionTitle {{ font-size: 19px; font-weight: 700; }}
            QLabel#muted {{ color: {colors['muted']}; font-size: 11px; }}
            QFrame#card, QFrame#section {{ background: {colors['surface']}; border: 1px solid {colors['line']}; border-radius: 8px; }}
            QPushButton {{ background: #2563a6; color: white; border: 0; border-radius: 5px; padding: 7px 14px; min-height: 18px; }}
            QPushButton:hover {{ background: #2f73bd; }}
            QPushButton:disabled {{ background: #4a525c; color: #b6bdc5; }}
            QPushButton#navButton {{ background: transparent; color: {colors['text']}; text-align: left; padding: 9px 10px; }}
            QPushButton#navButton:checked {{ background: {colors['select']}; }}
            QPushButton#secondaryButton {{ background: {colors['surface2']}; color: {colors['text']}; border: 1px solid {colors['line']}; }}
            QPushButton#dangerButton {{ background: #b42318; }}
            QPushButton#scanButton {{ background: #168a55; }}
            QPushButton#scanButton:disabled {{ background: #0f5f3d; }}
            QLineEdit, QComboBox, QPlainTextEdit, QScrollArea {{ background: {colors['input']}; color: {colors['text']}; border: 1px solid {colors['line']}; border-radius: 5px; padding: 6px; selection-background-color: #2563a6; }}
            QComboBox QAbstractItemView {{ background: {colors['surface']}; color: {colors['text']}; selection-background-color: {colors['select']}; }}
            QCheckBox {{ color: {colors['text']}; spacing: 7px; }}
            QTableView {{ background: {colors['bg']}; alternate-background-color: {colors['bg']}; color: {colors['text']}; border: 0; gridline-color: transparent; selection-background-color: {colors['select']}; selection-color: {colors['text']}; }}
            QHeaderView::section {{ background: {colors['surface2']}; color: {colors['text']}; padding: 8px; border: 0; border-right: 1px solid {colors['line']}; border-bottom: 1px solid {colors['line']}; font-weight: 600; }}
            QSplitter::handle {{ background: {colors['line']}; margin: 8px 2px; border-radius: 2px; }}
            QScrollBar:vertical {{ background: {colors['surface']}; width: 12px; margin: 0; }}
            QScrollBar::handle:vertical {{ background: #555d66; min-height: 28px; border-radius: 5px; }}
            QScrollBar:horizontal {{ background: {colors['surface']}; height: 12px; margin: 0; }}
            QScrollBar::handle:horizontal {{ background: #555d66; min-width: 28px; border-radius: 5px; }}
            QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
        """)
        for table in getattr(self, "data_tables", []):
            table.apply_appearance()

    def _sync_appearance(self) -> None:
        self._apply_tree_style()
