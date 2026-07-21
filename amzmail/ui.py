from __future__ import annotations

import queue
import os
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from tkinter import BooleanVar, StringVar, Tk, filedialog, messagebox
from tkinter import ttk

from amzmail import APP_NAME, APP_VERSION
from amzmail.db import AppDatabase
from amzmail.google_sheets import export_csv, post_to_google_sheet
from amzmail.imap_reader import PROVIDER_PRESETS, fetch_message_body, scan_account, test_connection
from amzmail.microsoft_graph import (
    fetch_microsoft_body,
    interactive_login,
    scan_microsoft_account,
    test_microsoft_connection,
)
from amzmail.updater import UpdateError, check_for_update, download_update, launch_update, normalize_repo
from amzmail.vault import Vault


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_UPDATE_REPO = "kienchuong/amazon-mail-reader-updates"


class AmazonMailReaderApp(Tk):
    def __init__(self, data_dir: Path, vault: Vault):
        super().__init__()
        self.title(f"{APP_NAME} {APP_VERSION}")
        self.geometry("1180x760")
        self.minsize(980, 640)

        self.data_dir = data_dir
        self.db = AppDatabase(data_dir / "amazon_mail_reader.db", vault)
        if not self.db.get_setting("github_repo").strip():
            self.db.set_setting("github_repo", DEFAULT_UPDATE_REPO)
        self.scan_queue: queue.Queue = queue.Queue()
        self.selected_account_id: int | None = None
        self.protocol("WM_DELETE_WINDOW", self.close_app)

        self._build_style()
        self._build_ui()
        self.refresh_accounts()
        self.refresh_inbox()
        self.refresh_payments()
        self.after(1200, self.check_updates_silently)

    def _build_style(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("Treeview", rowheight=26)
        style.configure("Heading.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Status.TLabel", foreground="#555")

    def _build_ui(self) -> None:
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=10)

        self.inbox_tab = ttk.Frame(self.notebook)
        self.payments_tab = ttk.Frame(self.notebook)
        self.accounts_tab = ttk.Frame(self.notebook)
        self.settings_tab = ttk.Frame(self.notebook)

        self.notebook.add(self.inbox_tab, text="Inbox")
        self.notebook.add(self.payments_tab, text="Payment")
        self.notebook.add(self.accounts_tab, text="Accounts")
        self.notebook.add(self.settings_tab, text="Cài đặt")

        self._build_inbox_tab()
        self._build_payments_tab()
        self._build_accounts_tab()
        self._build_settings_tab()

        self.status_var = StringVar(value="Sẵn sàng. App chỉ đọc mail, không gửi/xóa/sửa email.")
        ttk.Label(self, textvariable=self.status_var, style="Status.TLabel").pack(fill="x", padx=12, pady=(0, 8))

    def _build_inbox_tab(self) -> None:
        top = ttk.Frame(self.inbox_tab)
        top.pack(fill="x", padx=8, pady=8)

        ttk.Label(top, text="Loại").pack(side="left")
        self.category_filter = StringVar(value="All")
        category_box = ttk.Combobox(
            top,
            textvariable=self.category_filter,
            values=["All", "Payment", "Reject", "Amazon Account", "Amazon", "Security", "General"],
            width=18,
            state="readonly",
        )
        category_box.pack(side="left", padx=(6, 14))
        category_box.bind("<<ComboboxSelected>>", lambda _e: self.refresh_inbox())

        ttk.Label(top, text="Tìm").pack(side="left")
        self.search_var = StringVar()
        search = ttk.Entry(top, textvariable=self.search_var, width=34)
        search.pack(side="left", padx=(6, 8))
        search.bind("<Return>", lambda _e: self.refresh_inbox())

        ttk.Button(top, text="Tìm kiếm", command=self.refresh_inbox).pack(side="left", padx=4)
        ttk.Button(top, text="Quét tất cả", command=self.start_scan).pack(side="left", padx=4)

        ttk.Label(top, text="Số ngày").pack(side="left", padx=(18, 4))
        self.days_back_var = StringVar(value="30")
        ttk.Entry(top, textvariable=self.days_back_var, width=6).pack(side="left")

        ttk.Label(top, text="Giới hạn/account").pack(side="left", padx=(14, 4))
        self.max_messages_var = StringVar(value="300")
        ttk.Entry(top, textvariable=self.max_messages_var, width=7).pack(side="left")

        self.include_general_var = BooleanVar(value=False)
        ttk.Checkbutton(top, text="Lưu cả mail thường", variable=self.include_general_var).pack(side="left", padx=12)

        pane = ttk.PanedWindow(self.inbox_tab, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        list_frame = ttk.Frame(pane)
        detail_frame = ttk.Frame(pane)
        pane.add(list_frame, weight=3)
        pane.add(detail_frame, weight=2)

        columns = ("date", "account", "category", "priority", "from", "subject", "amount")
        self.inbox_tree = ttk.Treeview(list_frame, columns=columns, show="headings", selectmode="browse")
        headings = {
            "date": "Ngày",
            "account": "Account",
            "category": "Loại",
            "priority": "Mức",
            "from": "Người gửi",
            "subject": "Tiêu đề",
            "amount": "Payment",
        }
        widths = {"date": 145, "account": 110, "category": 105, "priority": 75, "from": 185, "subject": 320, "amount": 90}
        for col in columns:
            self.inbox_tree.heading(col, text=headings[col])
            self.inbox_tree.column(col, width=widths[col], anchor="w")
        self.inbox_tree.pack(side="left", fill="both", expand=True)
        yscroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.inbox_tree.yview)
        self.inbox_tree.configure(yscrollcommand=yscroll.set)
        yscroll.pack(side="right", fill="y")
        self.inbox_tree.bind("<<TreeviewSelect>>", self.on_message_selected)

        ttk.Label(detail_frame, text="Nội dung mail", style="Heading.TLabel").pack(anchor="w", pady=(0, 6))
        self.message_text = self._text_widget(detail_frame)
        self.message_text.insert("1.0", "Chọn một mail để đọc nội dung.")
        self.message_text.configure(state="disabled")

    def _build_payments_tab(self) -> None:
        top = ttk.Frame(self.payments_tab)
        top.pack(fill="x", padx=8, pady=8)
        ttk.Label(top, text="Thống kê payment", style="Heading.TLabel").pack(side="left")
        ttk.Button(top, text="Làm mới", command=self.refresh_payments).pack(side="right", padx=4)
        ttk.Button(top, text="Xuất CSV", command=self.export_payments_csv).pack(side="right", padx=4)

        self.payment_summary_var = StringVar(value="")
        ttk.Label(self.payments_tab, textvariable=self.payment_summary_var).pack(anchor="w", padx=8, pady=(0, 8))

        columns = ("date", "account", "email", "money", "payment_id")
        self.payment_tree = ttk.Treeview(self.payments_tab, columns=columns, show="headings")
        headings = {
            "date": "Ngày",
            "account": "Account",
            "email": "Email",
            "money": "Tiền",
            "payment_id": "Payment ID",
        }
        widths = {"date": 75, "account": 130, "email": 300, "money": 160, "payment_id": 220}
        for col in columns:
            self.payment_tree.heading(col, text=headings[col])
            self.payment_tree.column(col, width=widths[col], anchor="w")
        self.payment_tree.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    def _build_accounts_tab(self) -> None:
        pane = ttk.PanedWindow(self.accounts_tab, orient="horizontal")
        pane.pack(fill="both", expand=True, padx=8, pady=8)

        left = ttk.Frame(pane)
        right = ttk.Frame(pane)
        pane.add(left, weight=2)
        pane.add(right, weight=3)

        columns = ("name", "email", "provider", "status", "active")
        self.accounts_tree = ttk.Treeview(left, columns=columns, show="headings", selectmode="browse")
        for col, title, width in [
            ("name", "Account", 120),
            ("email", "Email", 190),
            ("provider", "Loại", 90),
            ("status", "Kết nối", 150),
            ("active", "Bật", 50),
        ]:
            self.accounts_tree.heading(col, text=title)
            self.accounts_tree.column(col, width=width, anchor="w")
        self.accounts_tree.pack(fill="both", expand=True)
        self.accounts_tree.bind("<<TreeviewSelect>>", self.on_account_selected)

        buttons = ttk.Frame(left)
        buttons.pack(fill="x", pady=(8, 0))
        ttk.Button(buttons, text="Làm mới", command=self.refresh_accounts).pack(side="left", padx=3)
        ttk.Button(buttons, text="Xóa account khỏi app", command=self.delete_selected_account).pack(side="left", padx=3)

        ttk.Label(right, text="Thông tin account", style="Heading.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")
        right.columnconfigure(1, weight=1)

        self.acc_name = StringVar()
        self.acc_email = StringVar()
        self.acc_provider = StringVar(value="Outlook")
        self.acc_host = StringVar(value="")
        self.acc_port = StringVar(value="993")
        self.acc_username = StringVar()
        self.acc_password = StringVar()
        self.acc_folder = StringVar(value="INBOX")
        self.acc_ssl = BooleanVar(value=True)
        self.acc_active = BooleanVar(value=True)

        self.account_field_widgets = []
        fields = [
            ("Tên account", self.acc_name, "entry"),
            ("Email nhận mail", self.acc_email, "entry"),
            ("Loại mail", self.acc_provider, "provider"),
            ("IMAP host", self.acc_host, "entry"),
            ("IMAP port", self.acc_port, "entry"),
            ("Username", self.acc_username, "entry"),
            ("Password/App password", self.acc_password, "password"),
            ("Folder", self.acc_folder, "entry"),
        ]
        for idx, (label, var, kind) in enumerate(fields, start=1):
            label_widget = ttk.Label(right, text=label)
            label_widget.grid(row=idx, column=0, sticky="w", pady=5, padx=(0, 8))
            if kind == "provider":
                widget = ttk.Combobox(right, textvariable=var, values=list(PROVIDER_PRESETS.keys()), state="readonly")
                widget.bind("<<ComboboxSelected>>", lambda _e: self.on_provider_changed())
            else:
                show = "*" if kind == "password" else ""
                widget = ttk.Entry(right, textvariable=var, show=show)
            widget.grid(row=idx, column=1, sticky="ew", pady=5)
            if idx >= 4:
                self.account_field_widgets.append((label_widget, widget))

        self.ssl_check = ttk.Checkbutton(right, text="Dùng SSL", variable=self.acc_ssl)
        self.ssl_check.grid(row=9, column=1, sticky="w", pady=4)
        ttk.Checkbutton(right, text="Bật quét account này", variable=self.acc_active).grid(row=10, column=1, sticky="w", pady=4)

        action_row = ttk.Frame(right)
        action_row.grid(row=11, column=0, columnspan=2, sticky="ew", pady=(14, 0))
        self.microsoft_login_button = ttk.Button(action_row, text="Đăng nhập Microsoft", command=self.login_microsoft)
        self.microsoft_login_button.pack(side="left", padx=4)
        self.add_button = ttk.Button(action_row, text="Thêm IMAP", command=self.add_account)
        self.add_button.pack(side="left", padx=4)
        self.update_button = ttk.Button(action_row, text="Cập nhật", command=self.update_account)
        self.update_button.pack(side="left", padx=4)
        self.test_button = ttk.Button(action_row, text="Kiểm tra kết nối", command=self.test_current_account)
        self.test_button.pack(side="left", padx=4)
        ttk.Button(action_row, text="Xóa form", command=self.clear_account_form).pack(side="left", padx=4)

        self.account_note = StringVar()
        ttk.Label(right, textvariable=self.account_note, wraplength=540, foreground="#555").grid(
            row=12, column=0, columnspan=2, sticky="w", pady=(16, 0)
        )
        self.on_provider_changed()

    def _build_settings_tab(self) -> None:
        frame = ttk.Frame(self.settings_tab)
        frame.pack(fill="both", expand=True, padx=12, pady=12)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Kết nối Microsoft", style="Heading.TLabel").grid(row=0, column=0, columnspan=2, sticky="w")

        self.microsoft_client_id_var = StringVar(value=self.db.get_setting("microsoft_client_id"))
        ttk.Label(frame, text="Microsoft Client ID").grid(row=1, column=0, sticky="w", pady=8, padx=(0, 8))
        ttk.Entry(frame, textvariable=self.microsoft_client_id_var).grid(row=1, column=1, sticky="ew", pady=8)
        ttk.Label(
            frame,
            text="Chỉ nhập một lần. Đây là mã công khai của ứng dụng Microsoft, không phải mật khẩu email.",
            foreground="#555",
        ).grid(row=2, column=1, sticky="w")

        ttk.Separator(frame).grid(row=3, column=0, columnspan=2, sticky="ew", pady=14)
        ttk.Label(frame, text="Xuất payment sang Google Sheet", style="Heading.TLabel").grid(row=4, column=0, columnspan=2, sticky="w")

        self.webhook_url_var = StringVar(value=self.db.get_setting("google_webhook_url"))
        self.webhook_secret_var = StringVar(value=self.db.get_secret_setting("google_webhook_secret"))
        self.google_auto_sync_var = BooleanVar(value=self.db.get_setting("google_auto_sync", "1") == "1")

        ttk.Label(frame, text="Webhook URL").grid(row=5, column=0, sticky="w", pady=8, padx=(0, 8))
        ttk.Entry(frame, textvariable=self.webhook_url_var).grid(row=5, column=1, sticky="ew", pady=8)
        ttk.Label(frame, text="Secret").grid(row=6, column=0, sticky="w", pady=8, padx=(0, 8))
        ttk.Entry(frame, textvariable=self.webhook_secret_var, show="*").grid(row=6, column=1, sticky="ew", pady=8)

        buttons = ttk.Frame(frame)
        buttons.grid(row=7, column=1, sticky="w", pady=(6, 12))
        ttk.Button(buttons, text="Lưu cấu hình", command=self.save_sheet_settings).pack(side="left", padx=4)
        ttk.Button(buttons, text="Xuất lên Google Sheet", command=self.export_to_google_sheet).pack(side="left", padx=4)
        ttk.Checkbutton(
            frame,
            text="Tự đồng bộ sau khi quét",
            variable=self.google_auto_sync_var,
        ).grid(row=7, column=0, sticky="w", pady=(6, 12))

        instructions = (
            "File google_sheets_webhook.gs nằm cùng thư mục app. Tạo Google Sheet, mở Apps Script, dán nội dung file đó, "
            "đổi SECRET, deploy Web App, rồi dán URL vào đây. Nếu chưa cấu hình Google Sheet, dùng nút Xuất CSV ở tab Payment."
        )
        ttk.Label(frame, text=instructions, wraplength=760, foreground="#555").grid(row=8, column=0, columnspan=2, sticky="w")

        ttk.Separator(frame).grid(row=9, column=0, columnspan=2, sticky="ew", pady=14)
        ttk.Label(frame, text="Cập nhật ứng dụng", style="Heading.TLabel").grid(row=10, column=0, columnspan=2, sticky="w")
        self.github_repo_var = StringVar(value=self.db.get_setting("github_repo"))
        ttk.Label(frame, text="Kho GitHub").grid(row=11, column=0, sticky="w", pady=8, padx=(0, 8))
        ttk.Entry(frame, textvariable=self.github_repo_var).grid(row=11, column=1, sticky="ew", pady=8)
        update_buttons = ttk.Frame(frame)
        update_buttons.grid(row=12, column=1, sticky="w")
        ttk.Button(update_buttons, text="Lưu", command=self.save_app_settings).pack(side="left", padx=4)
        ttk.Button(update_buttons, text="Kiểm tra cập nhật", command=self.check_updates_interactive).pack(side="left", padx=4)
        ttk.Label(frame, text=f"Phiên bản hiện tại: {APP_VERSION} | Dữ liệu: {self.data_dir}", foreground="#555").grid(
            row=13, column=0, columnspan=2, sticky="w", pady=(10, 0)
        )

    def _text_widget(self, parent):
        import tkinter as tk

        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        text = tk.Text(frame, wrap="word", font=("Segoe UI", 10), relief="solid", borderwidth=1)
        yscroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        text.configure(yscrollcommand=yscroll.set)
        text.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")
        return text

    def on_provider_changed(self) -> None:
        provider = self.acc_provider.get()
        preset = PROVIDER_PRESETS[provider]
        self.acc_host.set(preset["host"])
        self.acc_port.set(str(preset["port"]))
        self.acc_folder.set(preset["folder"])
        self.acc_ssl.set(bool(preset["use_ssl"]))
        is_outlook = provider == "Outlook"
        for label, widget in self.account_field_widgets:
            if is_outlook:
                label.grid_remove()
                widget.grid_remove()
            else:
                label.grid()
                widget.grid()
        if is_outlook:
            self.ssl_check.grid_remove()
            self.microsoft_login_button.configure(state="normal")
            self.add_button.configure(state="disabled")
            self.test_button.configure(text="Kiểm tra Microsoft")
            self.account_note.set(
                "Bấm Đăng nhập Microsoft. Trình duyệt sẽ mở trang chính thức của Microsoft; app không nhìn thấy hoặc lưu mật khẩu email."
            )
        else:
            self.ssl_check.grid()
            self.microsoft_login_button.configure(state="disabled")
            self.add_button.configure(state="normal")
            self.test_button.configure(text="Test IMAP")
            self.account_note.set(
                "Gmail/Yahoo và email tên miền riêng dùng IMAP read-only. App dùng BODY.PEEK để không đánh dấu mail đã đọc."
            )

    def apply_provider_preset(self) -> None:
        self.on_provider_changed()

    def account_form_data(self) -> dict:
        return {
            "name": self.acc_name.get(),
            "email": self.acc_email.get(),
            "provider": self.acc_provider.get(),
            "host": self.acc_host.get(),
            "port": self.acc_port.get(),
            "username": self.acc_username.get(),
            "password": self.acc_password.get(),
            "folder": self.acc_folder.get(),
            "use_ssl": self.acc_ssl.get(),
            "active": self.acc_active.get(),
        }

    def validate_account_form(self, require_password: bool) -> bool:
        …811 tokens truncated…f account and account["auth_type"] == "microsoft_oauth":
            if not self.acc_name.get().strip():
                messagebox.showwarning("Thiếu tên", "Vui lòng nhập tên account.")
                return
            self.db.update_account_name_active(self.selected_account_id, self.acc_name.get(), self.acc_active.get())
            self.refresh_accounts()
            self.set_status("Đã cập nhật account Microsoft.")
            return
        update_password = bool(self.acc_password.get().strip())
        if not self.validate_account_form(require_password=False):
            return
        self.db.update_imap_account(self.selected_account_id, self.account_form_data(), update_password)
        self.refresh_accounts()
        self.set_status("Đã cập nhật account.")

    def delete_selected_account(self) -> None:
        selection = self.accounts_tree.selection()
        if not selection:
            return
        if not messagebox.askyesno("Xóa account khỏi app", "Chỉ xóa account và dữ liệu cục bộ trong app. Email gốc không bị ảnh hưởng. Tiếp tục?"):
            return
        self.db.delete_account(int(selection[0]))
        self.clear_account_form()
        self.refresh_accounts()
        self.refresh_inbox()
        self.refresh_payments()

    def test_current_account(self) -> None:
        if self.acc_provider.get() == "Outlook":
            if self.selected_account_id is None:
                messagebox.showinfo("Chưa có account", "Hãy bấm Đăng nhập Microsoft trước.")
                return
            account = self.db.get_account(self.selected_account_id)
            client_id = self.microsoft_client_id_var.get().strip()
            self.set_status("Đang kiểm tra Microsoft...")

            def microsoft_worker():
                try:
                    test_microsoft_connection(account, self.db, client_id)
                    self.scan_queue.put(("status", "Kết nối Microsoft thành công."))
                except Exception as exc:
                    self.db.set_connection_status(int(account["id"]), "Cần đăng nhập lại")
                    self.scan_queue.put(("error", f"Kết nối Microsoft thất bại: {exc}"))

            threading.Thread(target=microsoft_worker, daemon=True).start()
            self.after(150, self.poll_scan_queue)
            return
        if not self.validate_account_form(require_password=self.selected_account_id is None):
            return
        data = self.account_form_data()
        password = data["password"]
        if not password and self.selected_account_id is not None:
            account = self.db.get_account(self.selected_account_id)
            password = self.db.account_password(account)
        self.set_status("Đang test IMAP...")

        def worker():
            try:
                test_connection(data, password)
                self.scan_queue.put(("status", "Kết nối IMAP thành công."))
            except Exception as exc:
                self.scan_queue.put(("error", f"Kết nối thất bại: {exc}"))

        threading.Thread(target=worker, daemon=True).start()
        self.after(150, self.poll_scan_queue)

    def login_microsoft(self) -> None:
        client_id = self.microsoft_client_id_var.get().strip()
        if not client_id:
            messagebox.showwarning(
                "Chưa có Microsoft Client ID",
                "Mở tab Cài đặt, nhập Microsoft Client ID và bấm Lưu trước khi đăng nhập.",
            )
            self.notebook.select(self.settings_tab)
            return
        self.db.set_setting("microsoft_client_id", client_id)
        name = self.acc_name.get().strip()
        self.set_status("Đang mở trình duyệt để đăng nhập Microsoft...")

        def worker():
            try:
                login = interactive_login(client_id)
                account_id = self.db.add_or_update_microsoft_account(login.profile, login.token_json, name)
                self.scan_queue.put(("microsoft_login", (account_id, login.profile["email"])))
            except Exception as exc:
                self.scan_queue.put(("error", f"Đăng nhập Microsoft thất bại: {exc}"))

        threading.Thread(target=worker, daemon=True).start()
        self.after(150, self.poll_scan_queue)

    def start_scan(self) -> None:
        try:
            days = int(self.days_back_var.get())
            max_messages = int(self.max_messages_var.get())
        except ValueError:
            messagebox.showwarning("Sai thông tin", "Số ngày và giới hạn phải là số.")
            return
        accounts = self.db.get_accounts(active_only=True)
        if not accounts:
            messagebox.showinfo("Chưa có account", "Hãy thêm ít nhất một account ở tab Accounts.")
            return
        self.set_status(f"Đang quét {len(accounts)} account...")

        def worker():
            for account in accounts:
                try:
                    if account["auth_type"] == "microsoft_oauth":
                        result = scan_microsoft_account(
                            account,
                            self.db,
                            self.microsoft_client_id_var.get().strip(),
                            days,
                            max_messages,
                            self.include_general_var.get(),
                        )
                    else:
                        password = self.db.account_password(account)
                        result = scan_account(account, password, days, max_messages, self.include_general_var.get(), self.db)
                except Exception as exc:
                    result = type("Result", (), {"account_name": account["name"], "scanned": 0, "saved": 0, "error": str(exc)})
                self.scan_queue.put(("scan_result", result))
            self.scan_queue.put(("scan_done", None))

        threading.Thread(target=worker, daemon=True).start()
        self.after(150, self.poll_scan_queue)

    def poll_scan_queue(self) -> None:
        handled = False
        while True:
            try:
                kind, payload = self.scan_queue.get_nowait()
            except queue.Empty:
                break
            handled = True
            if kind == "scan_result":
                if payload.error:
                    self.set_status(f"{payload.account_name}: lỗi - {payload.error}")
                else:
                    self.set_status(f"{payload.account_name}: quét {payload.scanned}, lưu {payload.saved}.")
            elif kind == "scan_done":
                self.refresh_inbox()
                self.refresh_payments()
                self.set_status("Quét xong.")
                if self.google_auto_sync_var.get():
                    self.after(100, self.export_to_google_sheet)
            elif kind == "status":
                self.set_status(payload)
                self.refresh_accounts()
            elif kind == "error":
                self.set_status(payload)
                self.refresh_accounts()
                messagebox.showerror("Lỗi", payload)
            elif kind == "message_body":
                self.set_message_text(payload)
            elif kind == "microsoft_login":
                account_id, email = payload
                self.refresh_accounts()
                self.clear_account_form()
                self.accounts_tree.selection_set(str(account_id))
                self.accounts_tree.focus(str(account_id))
                self.on_account_selected()
                self.set_status(f"Đã kết nối Microsoft: {email}")
                messagebox.showinfo("Đăng nhập thành công", f"Đã kết nối account {email}.")
            elif kind == "update_available":
                self.handle_update_available(payload)
            elif kind == "update_downloaded":
                self.install_downloaded_update(payload)
            elif kind == "status_dialog":
                self.set_status(payload)
                messagebox.showinfo("Cập nhật", payload)
        if handled or threading.active_count() > 1:
            self.after(250, self.poll_scan_queue)

    def refresh_inbox(self) -> None:
        self.inbox_tree.delete(*self.inbox_tree.get_children())
        rows = self.db.list_messages(self.category_filter.get(), self.search_var.get().strip())
        for row in rows:
            amount = ""
            if row["amount"] is not None:
                amount = f"{row['amount']:,.2f} {row['currency'] or ''}".strip()
            self.inbox_tree.insert(
                "",
                "end",
                iid=str(row["id"]),
                values=(
                    self.short_date(row["mail_date"]),
                    row["account_name"],
                    row["category"],
                    row["priority"],
                    row["from_addr"],
                    row["subject"],
                    amount,
                ),
            )

    def on_message_selected(self, _event=None) -> None:
        selection = self.inbox_tree.selection()
        if not selection:
            return
        message = self.db.get_message(int(selection[0]))
        if not message:
            return
        header = (
            f"Account: {message['account_name']} <{message['account_email']}>\n"
            f"Ngày: {message['mail_date'] or ''}\n"
            f"Người gửi: {message['from_addr'] or ''}\n"
            f"Tiêu đề: {message['subject'] or ''}\n"
            f"Loại: {message['category']} | Mức: {message['priority']} | Sender chính thức: {'Có' if message['trusted_sender'] else 'Chưa chắc'}\n\n"
            f"Tóm tắt:\n{message['snippet'] or ''}\n\nĐang tải nội dung mail..."
        )
        self.set_message_text(header)

        def worker():
            try:
                account = self.db.get_account(int(message["account_id"]))
                if account["auth_type"] == "microsoft_oauth":
                    body = fetch_microsoft_body(
                        account, self.db, self.microsoft_client_id_var.get().strip(), message["uid"]
                    )
                else:
                    password = self.db.account_password(account)
                    body = fetch_message_body(account, password, message["uid"])
                text = header.replace("Đang tải nội dung mail...", "Nội dung:") + "\n\n" + (body or "[Không có nội dung text]")
                self.scan_queue.put(("message_body", text))
            except Exception as exc:
                self.scan_queue.put(("message_body", header.replace("Đang tải nội dung mail...", f"Không tải được nội dung: {exc}")))

        threading.Thread(target=worker, daemon=True).start()
        self.after(150, self.poll_message_queue)

    def poll_message_queue(self) -> None:
        try:
            while True:
                kind, payload = self.scan_queue.get_nowait()
                if kind == "message_body":
                    self.set_message_text(payload)
                else:
                    self.scan_queue.put((kind, payload))
                    break
        except queue.Empty:
            pass
        if threading.active_count() > 1:
            self.after(250, self.poll_message_queue)

    def set_message_text(self, value: str) -> None:
        self.message_text.configure(state="normal")
        self.message_text.delete("1.0", "end")
        self.message_text.insert("1.0", value)
        self.message_text.configure(state="disabled")

    def refresh_payments(self) -> None:
        self.payment_tree.delete(*self.payment_tree.get_children())
        totals = defaultdict(float)
        unknown = 0
        for row in self.db.list_payments():
            if row["amount"] is not None and row["currency"]:
                totals[row["currency"]] += float(row["amount"])
            else:
                unknown += 1
            amount = "" if row["amount"] is None else f"{row['amount']:,.2f}"
            money = " ".join(part for part in (row["currency"] or "", amount) if part)
            self.payment_tree.insert(
                "",
                "end",
                values=(
                    self.payment_date(row["mail_date"]),
                    row["account_name"],
                    row["account_email"],
                    money,
                    row["payment_id"] or "",
                ),
            )
        summary_parts = [f"{currency}: {amount:,.2f}" for currency, amount in sorted(totals.items())]
        if unknown:
            summary_parts.append(f"{unknown} mail chưa tách được số tiền")
        self.payment_summary_var.set(" | ".join(summary_parts) if summary_parts else "Chưa có payment.")

    def export_payments_csv(self) -> None:
        payments = self.db.list_payments()
        if not payments:
            messagebox.showinfo("Chưa có payment", "Chưa có dữ liệu payment để xuất.")
            return
        default = BASE_DIR / "payments_export.csv"
        path = filedialog.asksaveasfilename(
            title="Lưu CSV",
            defaultextension=".csv",
            initialfile=default.name,
            initialdir=str(BASE_DIR),
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        export_csv(payments, Path(path))
        self.set_status(f"Đã xuất CSV: {path}")

    def save_sheet_settings(self) -> None:
        self.db.set_setting("microsoft_client_id", self.microsoft_client_id_var.get().strip())
        self.db.set_setting("google_webhook_url", self.webhook_url_var.get().strip())
        self.db.set_secret_setting("google_webhook_secret", self.webhook_secret_var.get().strip())
        self.db.set_setting("google_auto_sync", "1" if self.google_auto_sync_var.get() else "0")
        self.set_status("Đã lưu cấu hình Microsoft và Google Sheet.")

    def save_app_settings(self) -> None:
        try:
            repo = normalize_repo(self.github_repo_var.get())
        except UpdateError as exc:
            messagebox.showwarning("Sai địa chỉ GitHub", str(exc))
            return
        self.db.set_setting("github_repo", repo)
        self.github_repo_var.set(repo)
        self.set_status("Đã lưu cấu hình cập nhật.")

    def check_updates_silently(self) -> None:
        repo = self.db.get_setting("github_repo").strip()
        if not repo:
            return
        self._start_update_check(repo, interactive=False)

    def check_updates_interactive(self) -> None:
        self.save_app_settings()
        repo = self.github_repo_var.get().strip()
        if not repo:
            messagebox.showinfo("Chưa cấu hình", "Chưa cấu hình nguồn cập nhật GitHub.")
            return
        self._start_update_check(repo, interactive=True)

    def _start_update_check(self, repo: str, interactive: bool) -> None:
        self.set_status("Đang kiểm tra cập nhật...")

        def worker():
            try:
                info = check_for_update(repo, APP_VERSION)
                if info:
                    self.scan_queue.put(("update_available", info))
                elif interactive:
                    self.scan_queue.put(("status_dialog", "Bạn đang dùng phiên bản mới nhất."))
                else:
                    self.scan_queue.put(("status", "Đã kiểm tra cập nhật."))
            except Exception as exc:
                if interactive:
                    self.scan_queue.put(("error", f"Kiểm tra cập nhật thất bại: {exc}"))
                else:
                    self.scan_queue.put(("status", f"Không kiểm tra được cập nhật: {exc}"))

        threading.Thread(target=worker, daemon=True).start()
        self.after(150, self.poll_scan_queue)

    def handle_update_available(self, info) -> None:
        if not messagebox.askyesno(
            "Có bản cập nhật",
            f"Có phiên bản {info.version}. Tải và cài đặt ngay?\n\nDữ liệu account nằm ở {self.data_dir} và sẽ được giữ nguyên.",
        ):
            self.set_status(f"Đã bỏ qua phiên bản {info.version}.")
            return
        self.set_status(f"Đang tải phiên bản {info.version}...")

        def worker():
            try:
                package = download_update(info, self.data_dir)
                self.scan_queue.put(("update_downloaded", package))
            except Exception as exc:
                self.scan_queue.put(("error", f"Tải cập nhật thất bại: {exc}"))

        threading.Thread(target=worker, daemon=True).start()
        self.after(150, self.poll_scan_queue)

    def install_downloaded_update(self, package: Path) -> None:
        try:
            launch_update(package, BASE_DIR, "run_app.bat", os.getpid())
        except Exception as exc:
            messagebox.showerror("Không cài được cập nhật", str(exc))
            return
        self.set_status("Đã tải xong. App sẽ đóng và mở lại sau khi cập nhật.")
        self.after(500, self.close_app)

    def close_app(self) -> None:
        try:
            self.db.close()
        finally:
            self.destroy()

    def export_to_google_sheet(self) -> None:
        self.save_sheet_settings()
        url = self.webhook_url_var.get().strip()
        secret = self.webhook_secret_var.get().strip()
        if not url or not secret:
            messagebox.showwarning("Thiếu cấu hình", "Vui lòng nhập Webhook URL và Secret.")
            return
        payments = self.db.list_payments()
        if not payments:
            messagebox.showinfo("Chưa có payment", "Chưa có dữ liệu payment để xuất.")
            return
        self.set_status("Đang xuất Google Sheet...")

        def worker():
            try:
                status, body = post_to_google_sheet(url, secret, payments)
                self.scan_queue.put(("status", f"Google Sheet trả về HTTP {status}: {body[:160]}"))
            except Exception as exc:
                self.scan_queue.put(("error", f"Xuất Google Sheet thất bại: {exc}"))

        threading.Thread(target=worker, daemon=True).start()
        self.after(150, self.poll_scan_queue)

    def set_status(self, value: str) -> None:
        self.status_var.set(value)

    @staticmethod
    def short_date(value: str | None) -> str:
        if not value:
            return ""
        try:
            return datetime.fromisoformat(value).strftime("%Y-%m-%d %H:%M")
        except Exception:
            return value[:16]

    @staticmethod
    def payment_date(value: str | None) -> str:
        if not value:
            return ""
        try:
            return datetime.fromisoformat(value).strftime("%d/%m")
        except Exception:
            return value[:10]
