from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from amzmail import APP_VERSION


class SettingsViewMixin:
    def _build_settings_view(self, parent: ctk.CTkFrame) -> None:
        scroll = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        scroll.grid(row=0, column=0, sticky="nsew", padx=20, pady=18)
        scroll.grid_columnconfigure(0, weight=1)

        microsoft = self._settings_section(scroll, "Káº¿t ná»‘i Microsoft", 0)
        self.microsoft_client_id_var = tk.StringVar(value=self.db.get_setting("microsoft_client_id"))
        self._setting_entry(microsoft, 0, "Microsoft Client ID", self.microsoft_client_id_var)
        ctk.CTkLabel(
            microsoft,
            text="Chá»‰ nháº­p má»™t láº§n. ÄÃ¢y lÃ  mÃ£ cÃ´ng khai cá»§a á»©ng dá»¥ng Microsoft, khÃ´ng pháº£i máº­t kháº©u email.",
            justify="left", anchor="w",
        ).grid(row=2, column=1, sticky="ew", padx=14, pady=(0, 12))

        gmail = self._settings_section(scroll, "Káº¿t ná»‘i Gmail", 1)
        self.google_client_id_var = tk.StringVar(value=self.db.get_setting("google_client_id"))
        self.google_client_secret_var = tk.StringVar(value=self.db.get_secret_setting("google_client_secret"))
        self._setting_entry(gmail, 0, "Google Client ID", self.google_client_id_var)
        self._setting_entry(gmail, 1, "Google Client secret", self.google_client_secret_var, show="*")
        ctk.CTkButton(gmail, text="LÆ°u Google Client ID", width=155, command=self.save_google_client_settings).grid(
            row=3, column=0, sticky="w", padx=14, pady=(0, 10)
        )
        ctk.CTkLabel(
            gmail,
            text="DÃ¹ng cho ÄÄƒng nháº­p Google. App chá»‰ xin quyá»n Ä‘á»c Gmail, khÃ´ng lÆ°u máº­t kháº©u Gmail. Náº¿u OAuth cÃ²n á»Ÿ Testing, Google sáº½ yÃªu cáº§u Ä‘Äƒng nháº­p láº¡i sau 7 ngÃ y.",
            justify="left", anchor="w",
        ).grid(row=4, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 12))

        google = self._settings_section(scroll, "Xuáº¥t payment sang Google Sheet", 2)
        self.webhook_url_var = tk.StringVar(value=self.db.get_setting("google_webhook_url"))
        self.webhook_secret_var = tk.StringVar(value=self.db.get_secret_setting("google_webhook_secret"))
        self.google_auto_sync_var = tk.BooleanVar(value=self.db.get_setting("google_auto_sync", "1") == "1")
        self._setting_entry(google, 0, "Webhook URL", self.webhook_url_var)
        self._setting_entry(google, 1, "Secret", self.webhook_secret_var, show="*")
        ctk.CTkSwitch(google, text="Tá»± Ä‘á»“ng bá»™ sau khi quÃ©t", variable=self.google_auto_sync_var).grid(
            row=3, column=0, sticky="w", padx=14, pady=10
        )
        google_actions = ctk.CTkFrame(google, fg_color="transparent")
        google_actions.grid(row=3, column=1, sticky="w", padx=10, pady=8)
        ctk.CTkButton(google_actions, text="LÆ°u cáº¥u hÃ¬nh", width=110, command=self.save_sheet_settings).pack(side="left", padx=4)
        ctk.CTkButton(google_actions, text="Xuáº¥t lÃªn Google Sheet", width=155, command=self.export_to_google_sheet).pack(side="left", padx=4)
        ctk.CTkLabel(
            google,
            text="Webhook URL vÃ  Secret Ä‘Æ°á»£c lÆ°u trong kho dá»¯ liá»‡u riÃªng. Náº¿u chÆ°a cáº¥u hÃ¬nh, dÃ¹ng Xuáº¥t CSV táº¡i mÃ n hÃ¬nh Payment.",
            justify="left", anchor="w", wraplength=820,
        ).grid(row=4, column=0, columnspan=2, sticky="ew", padx=14, pady=(2, 14))

        mobile = self._settings_section(scroll, "Mobile Dashboard", 3)
        self.mobile_function_url_var = tk.StringVar(value=self.db.get_setting("supabase_mobile_function_url"))
        self.mobile_dashboard_url_var = tk.StringVar(value=self.db.get_setting("supabase_mobile_dashboard_url"))
        self.mobile_sync_secret_var = tk.StringVar(value=self.db.get_secret_setting("supabase_mobile_sync_secret"))
        self.mobile_auto_sync_var = tk.BooleanVar(value=self.db.get_setting("mobile_auto_sync", "1") == "1")
        self._setting_entry(mobile, 0, "Supabase Function URL", self.mobile_function_url_var)
        self._setting_entry(mobile, 1, "Dashboard URL", self.mobile_dashboard_url_var)
        self._setting_entry(mobile, 2, "Sync Secret", self.mobile_sync_secret_var, show="*")
        ctk.CTkSwitch(mobile, text="Tá»± Ä‘á»“ng bá»™ sau khi quÃ©t", variable=self.mobile_auto_sync_var).grid(
            row=4, column=0, sticky="w", padx=14, pady=10
        )
        mobile_actions = ctk.CTkFrame(mobile, fg_color="transparent")
        mobile_actions.grid(row=4, column=1, sticky="w", padx=10, pady=8)
        ctk.CTkButton(mobile_actions, text="Äá»“ng bá»™ ngay", width=120, command=self.sync_mobile_dashboard).pack(side="left", padx=4)
        ctk.CTkButton(mobile_actions, text="Má»Ÿ dashboard", width=125, command=self.open_mobile_dashboard).pack(side="left", padx=4)
        ctk.CTkLabel(
            mobile,
            text="Mobile dÃ¹ng Supabase riÃªng, khÃ´ng dÃ¹ng Google Sheet hay Apps Script. Dashboard lÃ  link chá»‰ xem; khÃ´ng chia sáº» link nÃ y.",
            justify="left", anchor="w", wraplength=820,
        ).grid(row=5, column=0, columnspan=2, sticky="ew", padx=14, pady=(2, 14))

        updates = self._settings_section(scroll, "Cáº­p nháº­t á»©ng dá»¥ng", 4)
        self.github_repo_var = tk.StringVar(value=self.db.get_setting("github_repo"))
        self._setting_entry(updates, 0, "Kho GitHub", self.github_repo_var)
        update_actions = ctk.CTkFrame(updates, fg_color="transparent")
        update_actions.grid(row=2, column=1, sticky="w", padx=10, pady=(2, 8))
        ctk.CTkButton(update_actions, text="LÆ°u", width=80, command=self.save_app_settings).pack(side="left", padx=4)
        ctk.CTkButton(update_actions, text="Kiá»ƒm tra cáº­p nháº­t", width=140, command=self.check_updates_interactive).pack(side="left", padx=4)
        ctk.CTkLabel(
            updates, text=f"PhiÃªn báº£n hiá»‡n táº¡i: {APP_VERSION}  |  Dá»¯ liá»‡u: {self.data_dir}", anchor="w"
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
