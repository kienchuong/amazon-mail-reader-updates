from __future__ import annotations

import queue
import os
import threading
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

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
from amzmail.views import AccountsViewMixin, InboxViewMixin, PaymentsViewMixin, SettingsViewMixin, ShellViewMixin


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_UPDATE_REPO = "kienchuong/amazon-mail-reader-updates"


class AmazonMailReaderApp(
    ShellViewMixin,
    InboxViewMixin,
    PaymentsViewMixin,
    AccountsViewMixin,
    SettingsViewMixin,
    ctk.CTk,
):
    def __init__(self, data_dir: Path, vault: Vault):
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
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
        data = self.account_form_data()
        required = ["name", "email", "provider", "host", "port", "username"]
        if require_password:
            required.append("password")
        missing = [field for field in required if not str(data[field]).strip()]
        if missing:
            messagebox.showwarning("Thiếu thông tin", "Vui lòng nhập đủ thông tin account.")
            return False
        try:
            int(data["port"])
        except ValueError:
            messagebox.showwarning("Sai port", "IMAP port phải là số.")
            return False
        return True

    def refresh_accounts(self) -> None:
        self.accounts_tree.delete(*self.accounts_tree.get_children())
        for account in self.db.get_accounts():
            self.accounts_tree.insert(
                "",
                "end",
                iid=str(account["id"]),
                values=(
                    account["name"],
                    account["email"],
                    account["provider"],
                    account["connection_status"] or ("Đã lưu" if account["auth_type"] == "imap_password" else "Chưa kết nối"),
                    "Có" if account["active"] else "Không",
                ),
            )
        self.accounts_tree.fit_columns()

    def on_account_selected(self, _event=None) -> None:
        selection = self.accounts_tree.selection()
        if not selection:
            return
        account = self.db.get_account(int(selection[0]))
        if not account:
            return
        self.selected_account_id = int(account["id"])
        self.acc_name.set(account["name"])
        self.acc_email.set(account["email"])
        self.acc_provider.set(account["provider"])
        self.on_provider_changed()
        self.acc_host.set(account["host"])
        self.acc_port.set(str(account["port"]))
        self.acc_username.set(account["username"])
        self.acc_password.set("")
        self.acc_folder.set(account["folder"])
        self.acc_ssl.set(bool(account["use_ssl"]))
        self.acc_active.set(bool(account["active"]))

    def clear_account_form(self) -> None:
        self.selected_account_id = None
        self.acc_name.set("")
        self.acc_email.set("")
        self.acc_provider.set("Outlook")
        self.on_provider_changed()
        self.acc_username.set("")
        self.acc_password.set("")
        self.acc_active.set(True)

    def add_account(self) -> None:
        if self.acc_provider.get() == "Outlook":
            self.login_microsoft()
            return
        if not self.validate_account_form(require_password=True):
            return
        self.db.add_imap_account(self.account_form_data())
        self.clear_account_form()
        self.refresh_accounts()
        self.set_status("Đã thêm account.")

    def update_account(self) -> None:
        if self.selected_account_id is None:
            messagebox.showinfo("Chọn account", "Vui lòng chọn account cần cập nhật.")
            return
        account = self.db.get_account(self.selected_account_id)
        if account and account["auth_type"] == "microsoft_oauth":
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
            self.show_page("settings")
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
        self.inbox_tree.fit_columns()

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
        self.payment_tree.fit_columns()
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
