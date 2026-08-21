from __future__ import annotations

import os
import sqlite3
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QIcon, QKeyEvent
from PySide6.QtWidgets import QApplication

from amzmail.ui import AmazonMailReaderApp
from amzmail.resources import app_icon_path
from amzmail.vault import Vault


DATA_DIR = Path(r"E:\Payment Royalties APP")


class QtUiRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.qt_app = QApplication.instance() or QApplication([])
        cls.qt_app.setWindowIcon(QIcon(str(app_icon_path())))
        cls.vault = Vault.open_auto(DATA_DIR)

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        source = sqlite3.connect(DATA_DIR / "amazon_mail_reader.db")
        target = sqlite3.connect(self.data_dir / "amazon_mail_reader.db")
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
        self.update_patch = patch.object(AmazonMailReaderApp, "check_updates_silently", return_value=None)
        self.update_patch.start()
        self.window = AmazonMailReaderApp(self.data_dir, self.vault)

    def tearDown(self) -> None:
        self.window.close()
        self.qt_app.processEvents()
        self.update_patch.stop()
        self.temp_dir.cleanup()

    def wait_for(self, predicate, timeout: float = 3.0) -> bool:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.qt_app.processEvents()
            if predicate():
                return True
            time.sleep(0.02)
        return bool(predicate())

    def test_load_navigation_filter_and_selection(self) -> None:
        self.assertFalse(self.window.windowIcon().isNull())
        self.assertGreater(self.window.accounts_tree.model.rowCount(), 0)
        self.assertGreater(self.window.inbox_tree.model.rowCount(), 0)
        self.assertGreater(self.window.payment_tree.model.rowCount(), 0)
        for page in ("inbox", "payments", "accounts", "settings"):
            self.window.show_page(page)
            self.assertIs(self.window.content.currentWidget(), self.window.pages[page])

        self.window.search_var.set("Amazon")
        self.window.refresh_inbox()
        self.window.category_filter.set("Payment")
        self.window.refresh_inbox()
        self.window.category_filter.set("All")
        self.window.search_var.set("")
        self.window.refresh_current_range()

        account_id = self.window.accounts_tree.get_children()[0]
        self.window.accounts_tree.selection_set(account_id)
        self.window.on_account_selected()
        self.assertEqual(self.window.selected_account_id, int(account_id))
        self.assertTrue(self.window.acc_email.get())

    def test_message_body_uses_background_signal(self) -> None:
        message_id = self.window.inbox_tree.get_children()[0]
        with (
            patch("amzmail.ui.fetch_microsoft_body", return_value="QT BODY TEST"),
            patch("amzmail.ui.fetch_google_body", return_value="QT BODY TEST"),
            patch("amzmail.ui.fetch_message_body", return_value="QT BODY TEST"),
        ):
            self.window.inbox_tree.selection_set(message_id)
            self.window.on_message_selected()
            self.assertTrue(self.wait_for(lambda: "QT BODY TEST" in self.window.message_text.toPlainText()))

    def test_table_selection_sort_copy_and_resize(self) -> None:
        table = self.window.inbox_tree
        first_id = table.get_children()[0]
        table.selection_set(first_id)
        self.assertEqual(table.selection(), [first_id])
        table.model.sort(1, Qt.SortOrder.AscendingOrder)
        table.table.setColumnWidth(0, 180)
        self.assertEqual(table.table.columnWidth(0), 180)
        table.reset_columns()
        event = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_C, Qt.KeyboardModifier.ControlModifier)
        QApplication.sendEvent(table.table, event)
        self.assertTrue(QApplication.clipboard().text())

    def test_scan_flow_stays_background_and_refreshes(self) -> None:
        self.window.google_auto_sync_var.set(False)
        self.window.mobile_auto_sync_var.set(False)
        account = self.window.db.get_accounts()[0]
        result = SimpleNamespace(account_name=account["name"], scanned=4, saved=2, error=None)
        with patch.object(self.window, "_scan_one_account", return_value=result):
            self.window._start_account_scan([account], single_account=True)
            self.assertTrue(self.wait_for(lambda: not self.window.scan_running))
        self.assertIn("Đã quét xong account", self.window.status_var.get())
        self.assertTrue(self.window.scan_all_button.isEnabled())

    def test_account_add_update_delete_on_database_copy(self) -> None:
        before = len(self.window.db.get_accounts())
        self.window.acc_provider.set("Custom")
        self.window.on_provider_changed()
        self.window.acc_name.set("Qt Test Account")
        self.window.acc_email.set("qt-test@example.com")
        self.window.acc_host.set("imap.example.com")
        self.window.acc_port.set("993")
        self.window.acc_username.set("qt-test@example.com")
        self.window.acc_password.set("test-app-password")
        self.window.acc_folder.set("INBOX")
        self.window.add_account()
        self.assertEqual(len(self.window.db.get_accounts()), before + 1)
        created = next(account for account in self.window.db.get_accounts() if account["email"] == "qt-test@example.com")

        self.window.accounts_tree.selection_set(str(created["id"]))
        self.window.on_account_selected()
        self.window.acc_name.set("Qt Test Updated")
        self.window.update_account()
        self.assertEqual(self.window.db.get_account(int(created["id"]))["name"], "Qt Test Updated")

        self.window.accounts_tree.selection_set(str(created["id"]))
        with patch("amzmail.ui.messagebox.askyesno", return_value=True):
            self.window.delete_selected_account()
        self.assertEqual(len(self.window.db.get_accounts()), before)

    def test_google_and_mobile_sync_callbacks_with_mock_network(self) -> None:
        with patch("amzmail.ui.post_to_google_sheet", return_value=(200, '{"ok":true}')):
            self.window.export_to_google_sheet()
            self.assertTrue(self.wait_for(lambda: "Google Sheet trả về HTTP 200" in self.window.status_var.get()))
        with (
            patch("amzmail.ui.CloudflareSyncService.post_snapshot", return_value=(200, '{"ok":true}')),
            patch.object(self.window, "_mobile_body", return_value="TEST BODY"),
        ):
            self.window.mobile_function_url_var.set("https://worker.example.test")
            self.window.sync_mobile_dashboard()
            self.assertTrue(self.wait_for(lambda: "Mobile Dashboard trả về HTTP 200" in self.window.status_var.get()))

    def test_csv_settings_and_reopen_database(self) -> None:
        csv_path = self.data_dir / "payments.csv"
        with patch("amzmail.ui.filedialog.asksaveasfilename", return_value=str(csv_path)):
            self.window.export_payments_csv()
        self.assertTrue(csv_path.is_file())
        self.assertGreater(csv_path.stat().st_size, 0)

        repo = self.window.github_repo_var.get()
        self.window.save_app_settings()
        self.assertEqual(self.window.db.get_setting("github_repo"), repo)
        self.window.save_sheet_settings()
        self.assertEqual(
            self.window.db.get_setting("cloudflare_mobile_worker_url"),
            self.window.mobile_function_url_var.get().strip(),
        )
        account_count = self.window.accounts_tree.model.rowCount()
        self.window.close()
        self.qt_app.processEvents()
        self.window = AmazonMailReaderApp(self.data_dir, self.vault)
        self.assertEqual(self.window.accounts_tree.model.rowCount(), account_count)


if __name__ == "__main__":
    unittest.main()
