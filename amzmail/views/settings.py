from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from amzmail import APP_VERSION


class SettingsViewMixin:
    def _build_settings_view(self, parent: ctk.CTkFrame) -> None:
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=20, pady=18)
        scroll.grid_columnconfigure(0, weight=1)

        microsoft = self._settings_section(scroll, "Kết nối Microsoft", 0)
        self.microsoft_client_id_var = tk.StringVar(value=self.db.get_setting("microsoft_client_id"))
        self._setting_entry(microsoft, 0, "Microsoft Client ID", self.microsoft_client_id_var)
        ctk.CTkLabel(
            microsoft,
            text="Chỉ nhập một lần. Đây là mã công khai của ứng dụng Microsoft, không phải mật khẩu email.",
            justify="left", anchor="w",
        ).grid(row=2, column=1, sticky="ew", padx=14, pady=(0, 12))

        gmail = self._settings_section(scroll, "Kết nối Gmail", 1)
        self.google_client_id_var = tk.StringVar(value=self.db.get_setting("google_client_id"))
        self._setting_entry(gmail, 0, "Google Client ID", self.google_client_id_var)
        ctk.CTkButton(gmail, text="Lưu Google Client ID", width=155, command=self.save_google_client_settings).grid(
            row=2, column=0, sticky="w", padx=14, pady=(0, 10)
        )
        ctk.CTkLabel(
            gmail,
            text="Dùng cho Đăng nhập Google. App chỉ xin quyền đọc Gmail, không lưu mật khẩu Gmail. Nếu OAuth còn ở Testing, Google sẽ yêu cầu đăng nhập lại sau 7 ngày.",
            justify="left", anchor="w",
        ).grid(row=3, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 12))

        google = self._settings_section(scroll, "Xuất payment sang Google Sheet", 2)
        self.webhook_url_var = tk.StringVar(value=self.db.get_setting("google_webhook_url"))
        self.webhook_secret_var = tk.StringVar(value=self.db.get_secret_setting("google_webhook_secret"))
        self.google_auto_sync_var = tk.BooleanVar(value=self.db.get_setting("google_auto_sync", "1") == "1")
        self._setting_entry(google, 0, "Webhook URL", self.webhook_url_var)
        self._setting_entry(google, 1, "Secret", self.webhook_secret_var, show="*")
        ctk.CTkSwitch(google, text="Tự đồng bộ sau khi quét", variable=self.google_auto_sync_var).grid(
            row=3, column=0, sticky="w", padx=14, pady=10
        )
        google_actions = ctk.CTkFrame(google, fg_color="transparent")
        google_actions.grid(row=3, column=1, sticky="w", padx=10, pady=8)
        ctk.CTkButton(google_actions, text="Lưu cấu hình", width=110, command=self.save_sheet_settings).pack(side="left", padx=4)
        ctk.CTkButton(google_actions, text="Xuất lên Google Sheet", width=155, command=self.export_to_google_sheet).pack(side="left", padx=4)
        ctk.CTkLabel(
            google,
            text="Webhook URL và Secret được lưu trong kho dữ liệu riêng. Nếu chưa cấu hình, dùng Xuất CSV tại màn hình Payment.",
            justify="left", anchor="w", wraplength=820,
        ).grid(row=4, column=0, columnspan=2, sticky="ew", padx=14, pady=(2, 14))

        updates = self._settings_section(scroll, "Cập nhật ứng dụng", 3)
        self.github_repo_var = tk.StringVar(value=self.db.get_setting("github_repo"))
        self._setting_entry(updates, 0, "Kho GitHub", self.github_repo_var)
        update_actions = ctk.CTkFrame(updates, fg_color="transparent")
        update_actions.grid(row=2, column=1, sticky="w", padx=10, pady=(2, 8))
        ctk.CTkButton(update_actions, text="Lưu", width=80, command=self.save_app_settings).pack(side="left", padx=4)
        ctk.CTkButton(update_actions, text="Kiểm tra cập nhật", width=140, command=self.check_updates_interactive).pack(side="left", padx=4)
        ctk.CTkLabel(
            updates, text=f"Phiên bản hiện tại: {APP_VERSION}  |  Dữ liệu: {self.data_dir}", anchor="w"
        ).grid(row=3, column=0, columnspan=2, sticky="ew", padx=14, pady=(2, 14))

        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)

    @staticmethod
    def _settings_section(parent: ctk.CTkFrame, title: str, row: int) -> ctk.CTkFrame:
        section = ctk.CTkFrame(parent, corner_radius=6)
        section.grid(row=row, column=0, sticky="ew", pady=(0, 14))
        section.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(section, text=title, font=ctk.CTkFont(size=17, weight="bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", padx=14, pady=(12, 8)
        )
        section._content_row = 1
        return section

    @staticmethod
    def _setting_entry(parent: ctk.CTkFrame, offset: int, label: str, variable: tk.StringVar, show: str = "") -> None:
        row = parent._content_row + offset
        ctk.CTkLabel(parent, text=label, anchor="w").grid(row=row, column=0, sticky="w", padx=14, pady=7)
        ctk.CTkEntry(parent, textvariable=variable, show=show).grid(row=row, column=1, sticky="ew", padx=14, pady=7)
