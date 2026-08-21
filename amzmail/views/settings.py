from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from amzmail import APP_VERSION
from amzmail.remote_sync import RemoteSyncConfig
from amzmail.views.controls import ValueBinding


class SettingsViewMixin:
    def _build_settings_view(self, parent: QWidget) -> None:
        page = QVBoxLayout(parent)
        page.setContentsMargins(20, 18, 20, 18)
        scroll = QScrollArea(parent)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(14)
        scroll.setWidget(content)
        page.addWidget(scroll)

        microsoft, microsoft_layout = self._settings_section("Kết nối Microsoft")
        self.microsoft_client_id_var = self._setting_entry(
            microsoft_layout, 1, "Microsoft Client ID", self.db.get_setting("microsoft_client_id")
        )
        microsoft_note = QLabel("Chỉ nhập một lần. Đây là mã công khai của ứng dụng Microsoft, không phải mật khẩu email.")
        microsoft_note.setWordWrap(True)
        microsoft_note.setObjectName("muted")
        microsoft_layout.addWidget(microsoft_note, 2, 1)
        content_layout.addWidget(microsoft)

        gmail, gmail_layout = self._settings_section("Kết nối Gmail")
        self.google_client_id_var = self._setting_entry(
            gmail_layout, 1, "Google Client ID", self.db.get_setting("google_client_id")
        )
        self.google_client_secret_var = self._setting_entry(
            gmail_layout, 2, "Google Client secret", self.db.get_secret_setting("google_client_secret"), password=True
        )
        save_google = QPushButton("Lưu Google Client ID")
        save_google.clicked.connect(self.save_google_client_settings)
        gmail_layout.addWidget(save_google, 3, 0)
        gmail_note = QLabel(
            "Dùng cho Đăng nhập Google. App chỉ xin quyền đọc Gmail, không lưu mật khẩu Gmail. "
            "Nếu OAuth còn ở Testing, Google sẽ yêu cầu đăng nhập lại sau 7 ngày."
        )
        gmail_note.setWordWrap(True)
        gmail_note.setObjectName("muted")
        gmail_layout.addWidget(gmail_note, 4, 0, 1, 2)
        content_layout.addWidget(gmail)

        google, google_layout = self._settings_section("Xuất payment sang Google Sheet")
        self.webhook_url_var = self._setting_entry(
            google_layout, 1, "Webhook URL", self.db.get_setting("google_webhook_url")
        )
        self.webhook_secret_var = self._setting_entry(
            google_layout, 2, "Secret", self.db.get_secret_setting("google_webhook_secret"), password=True
        )
        google_auto = QCheckBox("Tự đồng bộ sau khi quét")
        self.google_auto_sync_var = ValueBinding(google_auto, self.db.get_setting("google_auto_sync", "1") == "1")
        google_layout.addWidget(google_auto, 3, 0)
        google_actions = QHBoxLayout()
        save_sheet = QPushButton("Lưu cấu hình")
        save_sheet.clicked.connect(self.save_sheet_settings)
        export_sheet = QPushButton("Xuất lên Google Sheet")
        export_sheet.clicked.connect(self.export_to_google_sheet)
        google_actions.addWidget(save_sheet)
        google_actions.addWidget(export_sheet)
        google_actions.addStretch(1)
        google_layout.addLayout(google_actions, 3, 1)
        google_note = QLabel(
            "Webhook URL và Secret được lưu trong kho dữ liệu riêng. Nếu chưa cấu hình, dùng Xuất CSV tại màn hình Payment."
        )
        google_note.setWordWrap(True)
        google_note.setObjectName("muted")
        google_layout.addWidget(google_note, 4, 0, 1, 2)
        content_layout.addWidget(google)

        mobile_config = RemoteSyncConfig.from_database(self.db)
        mobile, mobile_layout = self._settings_section("Mobile Dashboard - Cloudflare")
        self.mobile_function_url_var = self._setting_entry(
            mobile_layout, 1, "Cloudflare Worker URL", mobile_config.worker_url
        )
        self.mobile_dashboard_url_var = self._setting_entry(
            mobile_layout, 2, "Dashboard URL", mobile_config.dashboard_url
        )
        self.mobile_sync_secret_var = self._setting_entry(
            mobile_layout, 3, "Sync Secret", mobile_config.sync_secret, password=True
        )
        self.mobile_timeout_var = self._setting_entry(
            mobile_layout, 4, "Timeout (giây)", str(mobile_config.timeout_seconds)
        )
        mobile_auto = QCheckBox("Tự đồng bộ sau khi quét")
        self.mobile_auto_sync_var = ValueBinding(mobile_auto, mobile_config.enabled)
        mobile_layout.addWidget(mobile_auto, 5, 0)
        mobile_actions = QHBoxLayout()
        sync_mobile = QPushButton("Đồng bộ ngay")
        sync_mobile.clicked.connect(self.sync_mobile_dashboard)
        open_mobile = QPushButton("Mở dashboard")
        open_mobile.clicked.connect(self.open_mobile_dashboard)
        mobile_actions.addWidget(sync_mobile)
        mobile_actions.addWidget(open_mobile)
        mobile_actions.addStretch(1)
        mobile_layout.addLayout(mobile_actions, 5, 1)
        mobile_note = QLabel(
            "Desktop gửi snapshot chỉ-đọc qua Cloudflare Worker; D1 không chứa mật khẩu email. "
            "Dashboard là link chỉ xem; không chia sẻ link này."
        )
        mobile_note.setWordWrap(True)
        mobile_note.setObjectName("muted")
        mobile_layout.addWidget(mobile_note, 6, 0, 1, 2)
        content_layout.addWidget(mobile)

        updates, updates_layout = self._settings_section("Cập nhật ứng dụng")
        self.github_repo_var = self._setting_entry(
            updates_layout, 1, "Kho GitHub", self.db.get_setting("github_repo")
        )
        update_actions = QHBoxLayout()
        save_update = QPushButton("Lưu")
        save_update.clicked.connect(self.save_app_settings)
        check_update = QPushButton("Kiểm tra cập nhật")
        check_update.clicked.connect(self.check_updates_interactive)
        update_actions.addWidget(save_update)
        update_actions.addWidget(check_update)
        update_actions.addStretch(1)
        updates_layout.addLayout(update_actions, 2, 1)
        current = QLabel(f"Phiên bản hiện tại: {APP_VERSION}  |  Dữ liệu: {self.data_dir}")
        current.setObjectName("muted")
        updates_layout.addWidget(current, 3, 0, 1, 2)
        content_layout.addWidget(updates)
        content_layout.addStretch(1)

    @staticmethod
    def _settings_section(title: str) -> tuple[QFrame, QGridLayout]:
        section = QFrame()
        section.setObjectName("section")
        layout = QGridLayout(section)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.setHorizontalSpacing(14)
        layout.setVerticalSpacing(8)
        layout.setColumnStretch(1, 1)
        heading = QLabel(title)
        heading.setObjectName("sectionTitle")
        layout.addWidget(heading, 0, 0, 1, 2)
        return section, layout

    @staticmethod
    def _setting_entry(layout: QGridLayout, row: int, label: str, value: str, *, password: bool = False) -> ValueBinding:
        layout.addWidget(QLabel(label), row, 0)
        entry = QLineEdit()
        if password:
            entry.setEchoMode(QLineEdit.EchoMode.Password)
        binding = ValueBinding(entry, value)
        layout.addWidget(entry, row, 1)
        return binding
