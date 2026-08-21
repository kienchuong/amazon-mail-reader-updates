from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtCore import Qt

from amzmail.imap_reader import PROVIDER_PRESETS
from amzmail.views.controls import ValueBinding


class AccountsViewMixin:
    def _build_accounts_view(self, parent: QWidget) -> None:
        page = QVBoxLayout(parent)
        page.setContentsMargins(20, 18, 20, 18)
        splitter = QSplitter(Qt.Orientation.Horizontal, parent)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        page.addWidget(splitter, 1)

        left = QFrame(splitter)
        left.setObjectName("card")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.setSpacing(8)
        columns = ("name", "email", "provider", "status", "active")
        headings = {"name": "Account", "email": "Email", "provider": "Loại", "status": "Kết nối", "active": "Bật"}
        widths = {"name": 115, "email": 185, "provider": 85, "status": 140, "active": 48}
        self.accounts_tree = self._create_tree(
            left,
            columns,
            headings,
            widths,
            center_columns=("name", "provider", "status", "active"),
            truncate_columns=("email",),
        )
        self.accounts_tree.bind("<<TreeviewSelect>>", self.on_account_selected)
        left_layout.addWidget(self.accounts_tree, 1)
        list_actions = QHBoxLayout()
        refresh = QPushButton("Làm mới")
        refresh.clicked.connect(self.refresh_accounts)
        delete = QPushButton("Xóa account")
        delete.setObjectName("dangerButton")
        delete.clicked.connect(self.delete_selected_account)
        list_actions.addWidget(refresh)
        list_actions.addWidget(delete)
        list_actions.addStretch(1)
        left_layout.addLayout(list_actions)

        right_scroll = QScrollArea(splitter)
        right_scroll.setWidgetResizable(True)
        right_scroll.setFrameShape(QFrame.Shape.NoFrame)
        right = QFrame()
        right.setObjectName("card")
        right_scroll.setWidget(right)
        form = QGridLayout(right)
        form.setContentsMargins(16, 14, 16, 16)
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(8)
        form.setColumnStretch(1, 1)
        title = QLabel("Thông tin account")
        title.setObjectName("sectionTitle")
        form.addWidget(title, 0, 0, 1, 2)

        self.account_field_widgets = []
        fields = [
            ("Tên account", "name", "entry"), ("Email nhận mail", "email", "entry"),
            ("Loại mail", "provider", "provider"), ("IMAP host", "host", "entry"),
            ("IMAP port", "port", "entry"), ("Username", "username", "entry"),
            ("Password/App password", "password", "password"), ("Folder", "folder", "entry"),
        ]
        values = {}
        for offset, (label_text, key, kind) in enumerate(fields, start=1):
            label = QLabel(label_text)
            if kind == "provider":
                widget = QComboBox()
                widget.addItems(list(PROVIDER_PRESETS))
                binding = ValueBinding(widget, "Outlook")
                widget.currentTextChanged.connect(lambda _value: self.on_provider_changed())
            else:
                widget = QLineEdit()
                if kind == "password":
                    widget.setEchoMode(QLineEdit.EchoMode.Password)
                binding = ValueBinding(widget)
            form.addWidget(label, offset, 0)
            form.addWidget(widget, offset, 1)
            values[key] = binding
            if offset >= 4:
                self.account_field_widgets.append((label, widget))

        self.acc_name = values["name"]
        self.acc_email = values["email"]
        self.acc_provider = values["provider"]
        self.acc_host = values["host"]
        self.acc_port = values["port"]
        self.acc_username = values["username"]
        self.acc_password = values["password"]
        self.acc_folder = values["folder"]
        self.acc_port.set("993")
        self.acc_folder.set("INBOX")

        self.ssl_check = QCheckBox("Dùng SSL")
        self.acc_ssl = ValueBinding(self.ssl_check, True)
        active_check = QCheckBox("Bật quét account này")
        self.acc_active = ValueBinding(active_check, True)
        form.addWidget(self.ssl_check, 9, 1)
        form.addWidget(active_check, 10, 1)

        actions = QGridLayout()
        self.microsoft_login_button = QPushButton("Đăng nhập Microsoft")
        self.microsoft_login_button.clicked.connect(self.login_microsoft)
        self.google_login_button = QPushButton("Đăng nhập Google")
        self.google_login_button.clicked.connect(self.login_google)
        self.add_button = QPushButton("Thêm IMAP")
        self.add_button.clicked.connect(self.add_account)
        self.update_button = QPushButton("Cập nhật")
        self.update_button.clicked.connect(self.update_account)
        self.test_button = QPushButton("Kiểm tra kết nối")
        self.test_button.clicked.connect(self.test_current_account)
        self.scan_one_button = QPushButton("Quét account này")
        self.scan_one_button.setObjectName("scanButton")
        self.scan_one_button.clicked.connect(self.start_selected_account_scan)
        clear = QPushButton("Xóa form")
        clear.setObjectName("secondaryButton")
        clear.clicked.connect(self.clear_account_form)
        actions.addWidget(self.microsoft_login_button, 0, 0)
        actions.addWidget(self.google_login_button, 0, 1)
        actions.addWidget(self.add_button, 0, 2)
        actions.addWidget(self.update_button, 0, 3)
        actions.addWidget(self.test_button, 1, 0, 1, 2)
        actions.addWidget(self.scan_one_button, 1, 2)
        actions.addWidget(clear, 1, 3)
        form.addLayout(actions, 11, 0, 1, 2)

        note = QLabel("")
        note.setWordWrap(True)
        note.setObjectName("muted")
        self.account_note = ValueBinding(note)
        form.addWidget(note, 12, 0, 1, 2)
        form.setRowStretch(13, 1)
        splitter.setSizes([500, 600])
        self.on_provider_changed()
