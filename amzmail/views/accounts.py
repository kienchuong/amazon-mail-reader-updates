from __future__ import annotations

import tkinter as tk

import customtkinter as ctk

from amzmail.imap_reader import PROVIDER_PRESETS


class AccountsViewMixin:
    def _build_accounts_view(self, parent: ctk.CTkFrame) -> None:
        body = ctk.CTkFrame(parent, fg_color="transparent")
        body.grid(row=0, column=0, sticky="nsew", padx=20, pady=18)
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=5, uniform="accounts")
        body.grid_columnconfigure(1, weight=6, uniform="accounts")

        left = ctk.CTkFrame(body, corner_radius=6)
        right = ctk.CTkScrollableFrame(body, corner_radius=6, label_text="Thông tin account")
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        right.grid_columnconfigure(1, weight=1)

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

        actions = ctk.CTkFrame(left, fg_color="transparent")
        actions.pack(fill="x", padx=10, pady=(0, 10))
        ctk.CTkButton(actions, text="Làm mới", width=90, command=self.refresh_accounts).pack(side="left")
        ctk.CTkButton(
            actions, text="Xóa account", width=110, fg_color="#b42318", hover_color="#912018",
            command=self.delete_selected_account,
        ).pack(side="left", padx=8)

        self.acc_name = tk.StringVar()
        self.acc_email = tk.StringVar()
        self.acc_provider = tk.StringVar(value="Outlook")
        self.acc_host = tk.StringVar(value="")
        self.acc_port = tk.StringVar(value="993")
        self.acc_username = tk.StringVar()
        self.acc_password = tk.StringVar()
        self.acc_folder = tk.StringVar(value="INBOX")
        self.acc_ssl = tk.BooleanVar(value=True)
        self.acc_active = tk.BooleanVar(value=True)

        self.account_field_widgets = []
        fields = [
            ("Tên account", self.acc_name, "entry"), ("Email nhận mail", self.acc_email, "entry"),
            ("Loại mail", self.acc_provider, "provider"), ("IMAP host", self.acc_host, "entry"),
            ("IMAP port", self.acc_port, "entry"), ("Username", self.acc_username, "entry"),
            ("Password/App password", self.acc_password, "password"), ("Folder", self.acc_folder, "entry"),
        ]
        for idx, (label, variable, kind) in enumerate(fields):
            label_widget = ctk.CTkLabel(right, text=label, anchor="w")
            label_widget.grid(row=idx, column=0, sticky="w", padx=(4, 12), pady=6)
            if kind == "provider":
                widget = ctk.CTkComboBox(
                    right, variable=variable, values=list(PROVIDER_PRESETS), state="readonly",
                    command=lambda _value: self.on_provider_changed(),
                )
            else:
                widget = ctk.CTkEntry(right, textvariable=variable, show="*" if kind == "password" else "")
            widget.grid(row=idx, column=1, sticky="ew", padx=(0, 4), pady=6)
            if idx >= 3:
                self.account_field_widgets.append((label_widget, widget))

        self.ssl_check = ctk.CTkSwitch(right, text="Dùng SSL", variable=self.acc_ssl)
        self.ssl_check.grid(row=8, column=1, sticky="w", pady=6)
        ctk.CTkSwitch(right, text="Bật quét account này", variable=self.acc_active).grid(row=9, column=1, sticky="w", pady=6)

        action_row = ctk.CTkFrame(right, fg_color="transparent")
        action_row.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        action_row.grid_columnconfigure((0, 1, 2), weight=1)
        self.microsoft_login_button = ctk.CTkButton(action_row, text="Đăng nhập Microsoft", command=self.login_microsoft)
        self.microsoft_login_button.grid(row=0, column=0, sticky="ew", padx=(0, 4), pady=4)
        self.add_button = ctk.CTkButton(action_row, text="Thêm IMAP", width=100, command=self.add_account)
        self.add_button.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        self.update_button = ctk.CTkButton(action_row, text="Cập nhật", width=90, command=self.update_account)
        self.update_button.grid(row=0, column=2, sticky="ew", padx=(4, 0), pady=4)
        self.test_button = ctk.CTkButton(action_row, text="Kiểm tra kết nối", command=self.test_current_account)
        self.test_button.grid(row=1, column=0, columnspan=2, sticky="ew", padx=(0, 4), pady=4)
        ctk.CTkButton(action_row, text="Xóa form", width=90, command=self.clear_account_form).grid(
            row=1, column=2, sticky="ew", padx=(4, 0), pady=4
        )

        self.account_note = tk.StringVar()
        ctk.CTkLabel(right, textvariable=self.account_note, wraplength=570, justify="left", anchor="w").grid(
            row=11, column=0, columnspan=2, sticky="ew", padx=4, pady=(14, 4)
        )
        self.on_provider_changed()

        parent.grid_rowconfigure(0, weight=1)
        parent.grid_columnconfigure(0, weight=1)
