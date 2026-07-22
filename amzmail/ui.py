from __future__ import annotations

import queue
import os
import threading
import webbrowser
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import customtkinter as ctk

from amzmail import APP_NAME, APP_VERSION
from amzmail.db import AppDatabase
from amzmail.google_sheets import export_csv, post_to_google_sheet
from amzmail.mobile_sync import build_mobile_snapshot
from amzmail.supabase_mobile import post_mobile_snapshot
from amzmail.google_gmail import (
    fetch_google_body,
    interactive_google_login,
    scan_google_account,
    test_google_connection,
)
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
        is_oauth = provider == "Outlook"
        for label, widget in self.account_field_widgets:
            if is_oauth:
                label.grid_remove()
                widget.grid_remove()
            else:
                label.grid()
                widget.grid()
        if provider == "Outlook":
            self.ssl_check.grid_remove()
            self.microsoft_login_button.configure(state="normal")
            self.google_login_button.configure(state="disabled")
            self.add_button.configure(state="disabled")
            self.test_button.configure(text="Kiá»ƒm tra Microsoft")
            self.account_note.set(
                "Báº¥m ÄÄƒng nháº­p Microsoft. TrÃ¬nh duyá»‡t sáº½ má»Ÿ trang chÃ­nh thá»©c cá»§a Microsoft; app khÃ´ng nhÃ¬n tháº¥y hoáº·c lÆ°u máº­t kháº©u email."
            )
        elif provider == "Google OAuth":
            self.ssl_check.grid_remove()
            self.microsoft_login_button.configure(state="disabled")
            self.google_login_button.configure(state="normal")
            self.add_button.configure(state="disabled")
            self.test_button.configure(text="Kiá»ƒm tra Google")
            self.account_note.set(
                "Báº¥m ÄÄƒng nháº­p Google. TrÃ¬nh duyá»‡t sáº½ má»Ÿ trang chÃ­nh thá»©c cá»§a Google; app khÃ´ng nhÃ¬n tháº¥y hoáº·c lÆ°u máº­t kháº©u Gmail."
            )
        else:
            self.ssl_check.grid()
            self.microsoft_login_button.configure(state="disabled")
            self.google_login_button.configure(state="disabled")
            self.add_button.configure(state="normal")
            self.test_button.configure(text="Test IMAP")
            self.account_note.set(
                "Gmail/Yahoo vÃ  email tÃªn miá»n riÃªng dÃ¹ng IMAP read-only. App dÃ¹ng BODY.PEEK Ä‘á»ƒ khÃ´ng Ä‘Ã¡nh dáº¥u mail Ä‘Ã£ Ä‘á»c."
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
            messagebox.showwarning("Thiáº¿u thÃ´ng tin", "Vui lÃ²ng nháº­p Ä‘á»§ thÃ´ng tin account.")
            return False
        try:
            int(data["port"])
        except ValueError:
            messagebox.showwarning("Sai port", "IMAP port pháº£i lÃ  sá»‘.")
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
                    account["connection_status"] or ("ÄÃ£ lÆ°u" if account["auth_type"] == "imap_password" else "ChÆ°a káº¿t ná»‘i"),
                    "CÃ³" if account["active"] else "KhÃ´ng",
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
        if self.acc_provider.get() == "Google OAuth":
            self.login_google()
            return
        if not self.validate_account_form(require_password=True):
            return
        self.db.add_imap_account(self.account_form_data())
        self.clear_account_form()
        self.refresh_accounts()
        self.set_status("ÄÃ£ thÃªm account.")

    def update_account(self) -> None:
        if self.selected_account_id is None:
            messagebox.showinfo("Chá»n account", "Vui lÃ²ng chá»n account cáº§n cáº­p nháº­t.")
            return
        account = self.db.get_account(self.selected_account_id)
        if account and account["auth_type"] in {"microsoft_oauth", "google_oauth"}:
            if not self.acc_name.get().strip():
                messagebox.showwarning("Thiáº¿u tÃªn", "Vui lÃ²ng nháº­p tÃªn account.")
                return
            self.db.update_account_name_active(self.selected_account_id, self.acc_name.get(), self.acc_active.get())
            self.refresh_accounts()
            self.set_status("ÄÃ£ cáº­p nháº­t account OAuth.")
            return
        update_password = bool(self.acc_password.get().strip())
        if not self.validate_account_form(require_password=False):
            return
        self.db.update_imap_account(self.selected_account_id, self.account_form_data(), update_password)
        self.refresh_accounts()
        self.set_status("ÄÃ£ cáº­p nháº­t account.")

    def delete_selected_account(self) -> None:
        selection = self.accounts_tree.selection()
        if not selection:
            return
        if not messagebox.askyesno("XÃ³a account khá»i app", "Chá»‰ xÃ³a account vÃ  dá»¯ liá»‡u cá»¥c bá»™ trong app. Email gá»‘c khÃ´ng bá»‹ áº£nh hÆ°á»Ÿng. Tiáº¿p tá»¥c?"):
            return
        self.db.delete_account(int(selection[0]))
        self.clear_account_form()
        self.refresh_accounts()
        self.refresh_inbox()
        self.refresh_payments()

    def test_current_account(self) -> None:
        if self.acc_provider.get() == "Outlook":
            if self.selected_account_id is None:
                messagebox.showinfo("ChÆ°a cÃ³ account", "HÃ£y báº¥m ÄÄƒng nháº­p Microsoft trÆ°á»›c.")
                return
            account = self.db.get_account(self.selected_account_id)
            client_id = self.microsoft_client_id_var.get().strip()
            self.set_status("Äang kiá»ƒm tra Microsoft...")

            def microsoft_worker():
                try:
                    test_microsoft_connection(account, self.db, client_id)
                    self.scan_queue.put(("status", "Káº¿t ná»‘i Microsoft thÃ nh cÃ´ng."))
                except Exception as exc:
                    self.db.set_connection_status(int(account["id"]), "Cáº§n Ä‘Äƒng nháº­p láº¡i")
                    self.scan_queue.put(("error", f"Káº¿t ná»‘i Microsoft tháº¥t báº¡i: {exc}"))

            threading.Thread(target=microsoft_worker, daemon=True).start()
            self.after(150, self.poll_scan_queue)
            return
        if self.acc_provider.get() == "Google OAuth":
            if self.selected_account_id is None:
                messagebox.showinfo("ChÆ°a cÃ³ account", "HÃ£y báº¥m ÄÄƒng nháº­p Google trÆ°á»›c.")
                return
            account = self.db.get_account(self.selected_account_id)
            client_id = self.google_client_id_var.get().strip()
            client_secret = self.google_client_secret_var.get().strip()
            self.set_status("Äang kiá»ƒm tra Google...")

            def google_worker():
                try:
                    test_google_connection(account, self.db, client_id, client_secret)
                    self.scan_queue.put(("status", "Káº¿t ná»‘i Google thÃ nh cÃ´ng."))
                except Exception as exc:
                    self.db.set_connection_status(int(account["id"]), "Cáº§n Ä‘Äƒng nháº­p Google láº¡i")
                    self.scan_queue.put(("error", f"Káº¿t ná»‘i Google tháº¥t báº¡i: {exc}"))

            threading.Thread(target=google_worker, daemon=True).start()
            self.after(150, self.poll_scan_queue)
            return
        if not self.validate_account_form(require_password=self.selected_account_id is None):
            return
        data = self.account_form_data()
        password = data["password"]
        if not password and self.selected_account_id is not None:
            account = self.db.get_account(self.selected_account_id)
            password = self.db.account_password(account)
        self.set_status("Äang test IMAP...")

        def worker():
            try:
                test_connection(data, password)
                self.scan_queue.put(("status", "Káº¿t ná»‘i IMAP thÃ nh cÃ´ng."))
            except Exception as exc:
                self.scan_queue.put(("error", f"Káº¿t ná»‘i tháº¥t báº¡i: {exc}"))

        threading.Thread(target=worker, daemon=True).start()
        self.after(150, self.poll_scan_queue)

    def login_microsoft(self) -> None:
        client_id = self.microsoft_client_id_var.get().strip()
        if not client_id:
            messagebox.showwarning(
                "ChÆ°a cÃ³ Microsoft Client ID",
                "Má»Ÿ tab CÃ i Ä‘áº·t, nháº­p Microsoft Client ID vÃ  báº¥m LÆ°u trÆ°á»›c khi Ä‘Äƒng nháº­p.",
            )
            self.show_page("settings")
            return
        self.db.set_setting("microsoft_client_id", client_id)
        name = self.acc_name.get().strip()
        self.set_status("Äang má»Ÿ Edge InPrivate Ä‘á»ƒ Ä‘Äƒng nháº­p Microsoft...")

        def worker():
            try:
                login = interactive_login(client_id)
                account_id = self.db.add_or_update_microsoft_account(login.profile, login.token_json, name)
                self.scan_queue.put(("microsoft_login", (account_id, login.profile["email"])))
            except Exception as exc:
                self.scan_queue.put(("error", f"ÄÄƒng nháº­p Microsoft tháº¥t báº¡i: {exc}"))

        threading.Thread(target=worker, daemon=True).start()
        self.after(150, self.poll_scan_queue)

    def login_google(self) -> None:
        client_id = self.google_client_id_var.get().strip()
        client_secret = self.google_client_secret_var.get().strip()
        if not client_id or not client_secret:
            messagebox.showwarning(
                "ChÆ°a cÃ³ Google Client ID",
                "Má»Ÿ tab CÃ i Ä‘áº·t, nháº­p Google Client ID vÃ  lÆ°u trÆ°á»›c khi Ä‘Äƒng nháº­p.",
            )
            self.show_page("settings")
            return
        self.db.set_setting("google_client_id", client_id)
        self.db.set_secret_setting("google_client_secret", client_secret)
        name = self.acc_name.get().strip()
        self.set_status("Äang má»Ÿ Edge InPrivate Ä‘á»ƒ Ä‘Äƒng nháº­p Google...")

        def worker():
            try:
                login = interactive_google_login(client_id, client_secret)
                account_id = self.db.add_or_update_google_account(login.profile, login.token_json, name)
                self.scan_queue.put(("google_login", (account_id, login.profile["email"])))
            except Exception as exc:
                self.scan_queue.put(("error", f"ÄÄƒng nháº­p Google tháº¥t báº¡i: {exc}"))

        threading.Thread(target=worker, daemon=True).start()
        self.after(150, self.poll_scan_queue)

    def start_scan(self) -> None:
        try:
            days = int(self.days_back_var.get())
            max_messages = int(self.max_messages_var.get())
        except ValueError:
            messagebox.showwarning("Sai thÃ´ng tin", "Sá»‘ ngÃ y vÃ  giá»›i háº¡n pháº£i lÃ  sá»‘.")
            return
        if days < 1 or max_messages < 1:
            messagebox.showwarning("Sai thÃ´ng tin", "Sá»‘ ngÃ y vÃ  giá»›i háº¡n pháº£i lá»›n hÆ¡n 0.")
            return
        accounts = self.db.get_accounts(active_only=True)
        if not accounts:
            messagebox.showinfo("ChÆ°a cÃ³ account", "HÃ£y thÃªm Ã­t nháº¥t má»™t account á»Ÿ tab Accounts.")
            return
        self.set_status(f"Äang quÃ©t {len(accounts)} account...")

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
                    elif account["auth_type"] == "google_oauth":
                        result = scan_google_account(
                            account,
                            self.db,
                            self.google_client_id_var.get().strip(),
                            self.google_client_secret_var.get().strip(),
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
                    self.set_status(f"{payload.account_name}: lá»—i - {payload.error}")
                else:
                    self.set_status(f"{payload.account_name}: quÃ©t {payload.scanned}, lÆ°u {payload.saved}.")
            elif kind == "scan_done":
                self.refresh_inbox()
                self.refresh_payments()
                self.set_status("QuÃ©t xong.")
                if self.google_auto_sync_var.get():
                    self.after(100, self.export_to_google_sheet)
                if self.mobile_auto_sync_var.get():
                    self.after(150, self.sync_mobile_dashboard)
            elif kind == "status":
                self.set_status(payload)
                self.refresh_accounts()
            elif kind == "error":
                self.set_status(payload)
                self.refresh_accounts()
                messagebox.showerror("Lá»—i", payload)
            elif kind == "message_body":
                self.set_message_text(payload)
            elif kind == "microsoft_login":
                account_id, email = payload
                self.refresh_accounts()
                self.clear_account_form()
                self.accounts_tree.selection_set(str(account_id))
                self.accounts_tree.focus(str(account_id))
                self.on_account_selected()
                self.set_status(f"ÄÃ£ káº¿t ná»‘i Microsoft: {email}")
                messagebox.showinfo("ÄÄƒng nháº­p thÃ nh cÃ´ng", f"ÄÃ£ káº¿t ná»‘i account {email}.")
            elif kind == "google_login":
                account_id, email = payload
                self.refresh_accounts()
                self.clear_account_form()
                self.acc_provider.set("Gmail")
                self.on_provider_changed()
                self.accounts_tree.selection_set(str(account_id))
                self.accounts_tree.focus(str(account_id))
                self.on_account_selected()
                self.set_status(f"ÄÃ£ káº¿t ná»‘i Google: {email}")
                messagebox.showinfo("ÄÄƒng nháº­p thÃ nh cÃ´ng", f"ÄÃ£ káº¿t ná»‘i Gmail {email}.")
            elif kind == "update_available":
                self.handle_update_available(payload)
            elif kind == "update_downloaded":
                self.install_downloaded_update(payload)
            elif kind == "status_dialog":
                self.set_status(payload)
                messagebox.showinfo("Cáº­p nháº­t", payload)
        if handled or threading.active_count() > 1:
            self.after(250, self.poll_scan_queue)

    def refresh_inbox(self) -> None:
        self.inbox_tree.delete(*self.inbox_tree.get_children())
        rows = self.db.list_messages(
            self.category_filter.get(), self.search_var.get().strip(), days_back=self.display_days()
        )
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

    def display_days(self) -> int:
        try:
            return max(int(self.days_back_var.get()), 1)
        except (TypeError, ValueError):
            return 7

    def refresh_current_range(self, _event=None) -> None:
        self.refresh_inbox()
        self.refresh_payments()

    def on_message_selected(self, _event=None) -> None:
        selection = self.inbox_tree.selection()
        if not selection:
            return
        message = self.db.get_message(int(selection[0]))
        if not message:
            return
        header = (
            f"Account: {message['account_name']} <{message['account_email']}>\n"
            f"NgÃ y: {message['mail_date'] or ''}\n"
            f"NgÆ°á»i gá»­i: {message['from_addr'] or ''}\n"
            f"TiÃªu Ä‘á»: {message['subject'] or ''}\n"
            f"Loáº¡i: {message['category']} | Má»©c: {message['priority']} | Sender chÃ­nh thá»©c: {'CÃ³' if message['trusted_sender'] else 'ChÆ°a cháº¯c'}\n\n"
            f"TÃ³m táº¯t:\n{message['snippet'] or ''}\n\nÄang táº£i ná»™i dung mail..."
        )
        self.set_message_text(header)

        def worker():
            try:
                account = self.db.get_account(int(message["account_id"]))
                if account["auth_type"] == "microsoft_oauth":
                    body = fetch_microsoft_body(
                        account, self.db, self.microsoft_client_id_var.get().strip(), message["uid"]
                    )
                elif account["auth_type"] == "google_oauth":
                    body = fetch_google_body(
                        account,
                        self.db,
                        self.google_client_id_var.get().strip(),
                        self.google_client_secret_var.get().strip(),
                        message["uid"],
                    )
                else:
                    password = self.db.account_password(account)
                    body = fetch_message_body(account, password, message["uid"])
                text = header.replace("Äang táº£i ná»™i dung mail...", "Ná»™i dung:") + "\n\n" + (body or "[KhÃ´ng cÃ³ ná»™i dung text]")
                self.scan_queue.put(("message_body", text))
            except Exception as exc:
                self.scan_queue.put(("message_body", header.replace("Äang táº£i ná»™i dung mail...", f"KhÃ´ng táº£i Ä‘Æ°á»£c ná»™i dung: {exc}")))

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
        for row in self.db.list_payments(self.display_days()):
            if row["amount"] is not None and row["currency"]:
                totals[row["currency"]] += float(row["amount"])
            else:
                unknown += 1
            amount = "" if row["amount"] is None else f"{row['amount']:,.2f}"
            self.payment_tree.insert(
                "",
                "end",
                values=(
                    self.payment_date(row["mail_date"]),
                    row["account_name"],
                    row["account_email"],
                    row["currency"] or "",
                    amount,
                    row["payment_id"] or "",
                ),
            )
        self.payment_tree.fit_columns()
        summary_parts = [f"{currency}: {amount:,.2f}" for currency, amount in sorted(totals.items())]
        if unknown:
            summary_parts.append(f"{unknown} mail chÆ°a tÃ¡ch Ä‘Æ°á»£c sá»‘ tiá»n")
        self.payment_summary_var.set(" | ".join(summary_parts) if summary_parts else "ChÆ°a cÃ³ payment.")

    def export_payments_csv(self) -> None:
        payments = self.db.list_payments(self.display_days())
        if not payments:
            messagebox.showinfo("ChÆ°a cÃ³ payment", "ChÆ°a cÃ³ dá»¯ liá»‡u payment Ä‘á»ƒ xuáº¥t.")
            return
        default = BASE_DIR / "payments_export.csv"
        path = filedialog.asksaveasfilename(
            title="LÆ°u CSV",
            defaultextension=".csv",
            initialfile=default.name,
            initialdir=str(BASE_DIR),
            filetypes=[("CSV", "*.csv")],
        )
        if not path:
            return
        export_csv(payments, Path(path))
        self.set_status(f"ÄÃ£ xuáº¥t CSV: {path}")

    def save_sheet_settings(self) -> None:
        self.db.set_setting("microsoft_client_id", self.microsoft_client_id_var.get().strip())
        self.db.set_setting("google_client_id", self.google_client_id_var.get().strip())
        self.db.set_secret_setting("google_client_secret", self.google_client_secret_var.get().strip())
        self.db.set_setting("google_webhook_url", self.webhook_url_var.get().strip())
        self.db.set_secret_setting("google_webhook_secret", self.webhook_secret_var.get().strip())
        self.db.set_setting("google_auto_sync", "1" if self.google_auto_sync_var.get() else "0")
        self.db.set_setting("supabase_mobile_function_url", self.mobile_function_url_var.get().strip())
        self.db.set_setting("supabase_mobile_dashboard_url", self.mobile_dashboard_url_var.get().strip())
        self.db.set_secret_setting("supabase_mobile_sync_secret", self.mobile_sync_secret_var.get().strip())
        self.db.set_setting("mobile_auto_sync", "1" if self.mobile_auto_sync_var.get() else "0")
        self.set_status("ÄÃ£ lÆ°u cáº¥u hÃ¬nh Microsoft vÃ  Google Sheet.")

    def save_google_client_settings(self) -> None:
        client_id = self.google_client_id_var.get().strip()
        if not client_id:
            messagebox.showwarning("Thiáº¿u Google Client ID", "HÃ£y nháº­p Google Client ID trÆ°á»›c khi lÆ°u.")
            return
        self.db.set_setting("google_client_id", client_id)
        self.db.set_secret_setting("google_client_secret", self.google_client_secret_var.get().strip())
        self.set_status("ÄÃ£ lÆ°u Google Client ID.")

    def save_app_settings(self) -> None:
        try:
            repo = normalize_repo(self.github_repo_var.get())
        except UpdateError as exc:
            messagebox.showwarning("Sai Ä‘á»‹a chá»‰ GitHub", str(exc))
            return
        self.db.set_setting("github_repo", repo)
        self.github_repo_var.set(repo)
        self.set_status("ÄÃ£ lÆ°u cáº¥u hÃ¬nh cáº­p nháº­t.")

    def check_updates_silently(self) -> None:
        repo = self.db.get_setting("github_repo").strip()
        if not repo:
            return
        self._start_update_check(repo, interactive=False)

    def check_updates_interactive(self) -> None:
        self.save_app_settings()
        repo = self.github_repo_var.get().strip()
        if not repo:
            messagebox.showinfo("ChÆ°a cáº¥u hÃ¬nh", "ChÆ°a cáº¥u hÃ¬nh nguá»“n cáº­p nháº­t GitHub.")
            return
        self._start_update_check(repo, interactive=True)

    def _start_update_check(self, repo: str, interactive: bool) -> None:
        self.set_status("Äang kiá»ƒm tra cáº­p nháº­t...")

        def worker():
            try:
                info = check_for_update(repo, APP_VERSION)
                if info:
                    self.scan_queue.put(("update_available", info))
                elif interactive:
                    self.scan_queue.put(("status_dialog", "Báº¡n Ä‘ang dÃ¹ng phiÃªn báº£n má»›i nháº¥t."))
                else:
                    self.scan_queue.put(("status", "ÄÃ£ kiá»ƒm tra cáº­p nháº­t."))
            except Exception as exc:
                if interactive:
                    self.scan_queue.put(("error", f"Kiá»ƒm tra cáº­p nháº­t tháº¥t báº¡i: {exc}"))
                else:
                    self.scan_queue.put(("status", f"KhÃ´ng kiá»ƒm tra Ä‘Æ°á»£c cáº­p nháº­t: {exc}"))

        threading.Thread(target=worker, daemon=True).start()
        self.after(150, self.poll_scan_queue)

    def handle_update_available(self, info) -> None:
        if not messagebox.askyesno(
            "CÃ³ báº£n cáº­p nháº­t",
            f"CÃ³ phiÃªn báº£n {info.version}. Táº£i vÃ  cÃ i Ä‘áº·t ngay?\n\nDá»¯ liá»‡u account náº±m á»Ÿ {self.data_dir} vÃ  sáº½ Ä‘Æ°á»£c giá»¯ nguyÃªn.",
        ):
            self.set_status(f"ÄÃ£ bá» qua phiÃªn báº£n {info.version}.")
            return
        self.set_status(f"Äang táº£i phiÃªn báº£n {info.version}...")

        def worker():
            try:
                package = download_update(info, self.data_dir)
                self.scan_queue.put(("update_downloaded", package))
            except Exception as exc:
                self.scan_queue.put(("error", f"Táº£i cáº­p nháº­t tháº¥t báº¡i: {exc}"))

        threading.Thread(target=worker, daemon=True).start()
        self.after(150, self.poll_scan_queue)

    def install_downloaded_update(self, package: Path) -> None:
        try:
            launch_update(package, BASE_DIR, "run_app.bat", os.getpid())
        except Exception as exc:
            messagebox.showerror("KhÃ´ng cÃ i Ä‘Æ°á»£c cáº­p nháº­t", str(exc))
            return
        self.set_status("ÄÃ£ táº£i xong. App sáº½ Ä‘Ã³ng vÃ  má»Ÿ láº¡i sau khi cáº­p nháº­t.")
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
            messagebox.showwarning("Thiáº¿u cáº¥u hÃ¬nh", "Vui lÃ²ng nháº­p Webhook URL vÃ  Secret.")
            return
        payments = self.db.list_payments(self.display_days())
        if not payments:
            messagebox.showinfo("ChÆ°a cÃ³ payment", "ChÆ°a cÃ³ dá»¯ liá»‡u payment Ä‘á»ƒ xuáº¥t.")
            return
        self.set_status("Äang xuáº¥t Google Sheet...")

        def worker():
            try:
                status, body = post_to_google_sheet(url, secret, payments)
                self.scan_queue.put(("status", f"Google Sheet tráº£ vá» HTTP {status}: {body[:160]}"))
            except Exception as exc:
                self.scan_queue.put(("error", f"Xuáº¥t Google Sheet tháº¥t báº¡i: {exc}"))

        threading.Thread(target=worker, daemon=True).start()
        self.after(150, self.poll_scan_queue)

    def _mobile_body(self, message) -> str:
        account = self.db.get_account(int(message["account_id"]))
        if not account:
            raise RuntimeError("KhÃ´ng tÃ¬m tháº¥y account cá»§a mail nÃ y.")
        if account["auth_type"] == "microsoft_oauth":
            return fetch_microsoft_body(account, self.db, self.microsoft_client_id_var.get().strip(), message["uid"])
        if account["auth_type"] == "google_oauth":
            return fetch_google_body(
                account,
                self.db,
                self.google_client_id_var.get().strip(),
                self.google_client_secret_var.get().strip(),
                message["uid"],
            )
        return fetch_message_body(account, self.db.account_password(account), message["uid"])

    def sync_mobile_dashboard(self) -> None:
        self.save_sheet_settings()
        url = self.mobile_function_url_var.get().strip()
        secret = self.mobile_sync_secret_var.get().strip()
        if not url or not secret:
            self.set_status("ChÆ°a Ä‘á»“ng bá»™ Mobile Dashboard: thiáº¿u Webhook URL hoáº·c Secret.")
            return
        days = self.display_days()
        messages = self.db.list_messages(days_back=days)
        payments = self.db.list_payments(days)
        self.set_status("Äang Ä‘á»“ng bá»™ Mobile Dashboard...")

        def worker():
            try:
                snapshot = build_mobile_snapshot(messages, payments, days, self._mobile_body)
                status, body = post_mobile_snapshot(url, secret, snapshot)
                self.scan_queue.put(("status", f"Mobile Dashboard tráº£ vá» HTTP {status}: {body[:120]}"))
            except Exception as exc:
                self.scan_queue.put(("error", f"Äá»“ng bá»™ Mobile Dashboard tháº¥t báº¡i: {exc}"))

        threading.Thread(target=worker, daemon=True).start()
        self.after(150, self.poll_scan_queue)

    def set_mobile_pin(self) -> None:
        self.save_sheet_settings()
        url = self.webhook_url_var.get().strip()
        secret = self.webhook_secret_var.get().strip()
        pin = self.mobile_pin_var.get().strip()
        if not url or not secret:
            messagebox.showwarning("Thiáº¿u cáº¥u hÃ¬nh", "HÃ£y nháº­p Webhook URL vÃ  Secret trÆ°á»›c.")
            return
        if len(pin) < 4:
            messagebox.showwarning("PIN quÃ¡ ngáº¯n", "PIN Mobile Dashboard cáº§n Ã­t nháº¥t 4 kÃ½ tá»±.")
            return
        self.set_status("Äang Ä‘áº·t PIN Mobile Dashboard...")

        def worker():
            try:
                status, body = post_mobile_action(url, secret, "mobile_set_pin", pin=pin)
                self.scan_queue.put(("status", f"ÄÃ£ Ä‘áº·t PIN Mobile Dashboard (HTTP {status}). {body[:120]}"))
            except Exception as exc:
                self.scan_queue.put(("error", f"KhÃ´ng Ä‘áº·t Ä‘Æ°á»£c PIN Mobile Dashboard: {exc}"))

        threading.Thread(target=worker, daemon=True).start()
        self.after(150, self.poll_scan_queue)

    def revoke_mobile_devices(self) -> None:
        if not messagebox.askyesno("Thu há»“i thiáº¿t bá»‹", "Táº¥t cáº£ Ä‘iá»‡n thoáº¡i vÃ  Mac Ä‘ang má»Ÿ dashboard sáº½ pháº£i nháº­p PIN láº¡i. Tiáº¿p tá»¥c?"):
            return
        self.save_sheet_settings()
        url = self.webhook_url_var.get().strip()
        secret = self.webhook_secret_var.get().strip()
        if not url or not secret:
            messagebox.showwarning("Thiáº¿u cáº¥u hÃ¬nh", "HÃ£y nháº­p Webhook URL vÃ  Secret trÆ°á»›c.")
            return
        self.set_status("Äang thu há»“i thiáº¿t bá»‹ Mobile Dashboard...")

        def worker():
            try:
                status, body = post_mobile_action(url, secret, "mobile_revoke_devices")
                self.scan_queue.put(("status", f"ÄÃ£ thu há»“i thiáº¿t bá»‹ Mobile Dashboard (HTTP {status}). {body[:120]}"))
            except Exception as exc:
                self.scan_queue.put(("error", f"KhÃ´ng thu há»“i Ä‘Æ°á»£c thiáº¿t bá»‹: {exc}"))

        threading.Thread(target=worker, daemon=True).start()
        self.after(150, self.poll_scan_queue)

    def open_mobile_dashboard(self) -> None:
        url = self.mobile_dashboard_url_var.get().strip()
        if not url:
            messagebox.showwarning("Thiáº¿u Webhook URL", "HÃ£y nháº­p Webhook URL trÆ°á»›c.")
            return
        webbrowser.open(url)

    def set_status(self, value: str) -> None:
        self.status_var.set(value)

    @staticmethod
    def short_date(value: str | None) -> str:
        if not value:
            return ""
        try:
            return datetime.fromisoformat(value).strftime("%d/%m")
        except Exception:
            return value[:10]

    @staticmethod
    def payment_date(value: str | None) -> str:
        if not value:
            return ""
        try:
            return datetime.fromisoformat(value).strftime("%d/%m")
        except Exception:
            return value[:10]
