from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from amzmail.views.controls import ValueBinding
from amzmail.views.data_table import FluentSplitPane


class InboxViewMixin:
    def _build_inbox_view(self, parent: QWidget) -> None:
        page = QVBoxLayout(parent)
        page.setContentsMargins(20, 18, 20, 18)
        page.setSpacing(12)

        toolbar = QHBoxLayout()
        toolbar.addWidget(QLabel("Loại"))
        category_box = QComboBox()
        category_box.addItems(["All", "Payment", "Reject", "Amazon Account", "Amazon", "Security", "General"])
        category_box.setMinimumWidth(170)
        self.category_filter = ValueBinding(category_box, "All")
        category_box.currentTextChanged.connect(lambda _value: self.refresh_inbox())
        toolbar.addWidget(category_box)

        search = QLineEdit()
        search.setPlaceholderText("Tìm tiêu đề hoặc người gửi")
        self.search_var = ValueBinding(search)
        search.returnPressed.connect(self.refresh_inbox)
        toolbar.addWidget(search, 1)
        search_button = QPushButton("Tìm kiếm")
        search_button.clicked.connect(self.refresh_inbox)
        toolbar.addWidget(search_button)
        self.scan_all_button = QPushButton("Quét tất cả")
        self.scan_all_button.clicked.connect(self.start_scan)
        toolbar.addWidget(self.scan_all_button)
        page.addLayout(toolbar)

        options = QHBoxLayout()
        options.addWidget(QLabel("Số ngày quét/hiển thị"))
        days_entry = QLineEdit("7")
        days_entry.setFixedWidth(65)
        self.days_back_var = ValueBinding(days_entry, "7")
        days_entry.returnPressed.connect(self.refresh_current_range)
        days_entry.editingFinished.connect(self.refresh_current_range)
        options.addWidget(days_entry)
        options.addSpacing(10)
        options.addWidget(QLabel("Giới hạn/account"))
        max_entry = QLineEdit("300")
        max_entry.setFixedWidth(75)
        self.max_messages_var = ValueBinding(max_entry, "300")
        options.addWidget(max_entry)
        options.addSpacing(10)
        include_general = QCheckBox("Lưu cả mail thường")
        self.include_general_var = ValueBinding(include_general, False)
        options.addWidget(include_general)
        options.addStretch(1)
        page.addLayout(options)

        pane = FluentSplitPane(parent)
        self.inbox_pane = pane
        list_layout = QVBoxLayout(pane.left)
        list_layout.setContentsMargins(0, 0, 0, 0)
        detail_layout = QVBoxLayout(pane.right)
        detail_layout.setContentsMargins(12, 12, 12, 12)
        detail_layout.setSpacing(8)

        columns = ("date", "account", "category", "priority", "from", "subject", "amount")
        headings = {
            "date": "Ngày", "account": "Account", "category": "Loại", "priority": "Mức",
            "from": "Người gửi", "subject": "Tiêu đề", "amount": "Payment",
        }
        widths = {"date": 132, "account": 105, "category": 105, "priority": 72, "from": 180, "subject": 310, "amount": 100}
        self.inbox_tree = self._create_tree(
            pane.left,
            columns,
            headings,
            widths,
            center_columns=("date", "account", "category", "priority", "amount"),
            truncate_columns=("from", "subject"),
            status_columns=("category", "priority"),
        )
        self.inbox_tree.bind("<<TreeviewSelect>>", self.on_message_selected)
        list_layout.addWidget(self.inbox_tree)

        detail_title = QLabel("Nội dung mail")
        detail_title.setObjectName("sectionTitle")
        detail_layout.addWidget(detail_title)
        self.message_text = QPlainTextEdit("Chọn một mail để đọc nội dung.")
        self.message_text.setReadOnly(True)
        self.message_text.setLineWrapMode(QPlainTextEdit.LineWrapMode.WidgetWidth)
        detail_layout.addWidget(self.message_text, 1)
        page.addWidget(pane, 1)
