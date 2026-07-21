import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from amzmail.db import AppDatabase
from amzmail.google_sheets import GOOGLE_SHEET_COLUMNS, google_sheet_rows


class PlainVault:
    def encrypt(self, value):
        return value

    def decrypt(self, value):
        return value


class RangeAndSheetTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = AppDatabase(Path(self.temp_dir.name) / "test.db", PlainVault())
        self.account_id = self.db.add_imap_account(
            {
                "name": "Account 02",
                "email": "account@example.com",
                "provider": "Custom",
                "host": "mail.example.com",
                "port": 993,
                "username": "account@example.com",
                "password": "app-password",
            }
        )

    def tearDown(self):
        self.db.close()
        self.temp_dir.cleanup()

    def _save_payment(self, uid, mail_date):
        self.db.upsert_message(
            {
                "account_id": self.account_id,
                "folder": "INBOX",
                "uid": uid,
                "mail_date": mail_date,
                "from_addr": "payments@amazon.com",
                "subject": f"Payment {uid}",
                "category": "Payment",
                "priority": "Normal",
                "trusted_sender": True,
                "currency": "USD",
                "amount": 12.5,
                "payment_id": uid,
                "snippet": "Payment",
            }
        )

    def test_range_filters_messages_and_payments(self):
        now = datetime.now().astimezone()
        self._save_payment("recent", now.isoformat(timespec="seconds"))
        self._save_payment("old", (now - timedelta(days=8)).isoformat(timespec="seconds"))

        self.assertEqual([row["payment_id"] for row in self.db.list_messages(days_back=7)], ["recent"])
        self.assertEqual([row["payment_id"] for row in self.db.list_payments(days_back=7)], ["recent"])
        self.assertEqual({row["payment_id"] for row in self.db.list_payments(days_back=14)}, {"recent", "old"})

    def test_google_sheet_payload_has_only_requested_columns(self):
        rows = google_sheet_rows(
            [{"mail_date": "2026-07-20T14:19:00Z", "account_name": "Acc 77", "currency": "USD", "amount": 280.35, "payment_id": "P-1"}]
        )
        self.assertEqual(GOOGLE_SHEET_COLUMNS, ["mail_date", "account_name", "currency", "amount", "payment_id"])
        self.assertEqual(rows, [{"mail_date": "2026-07-20T14:19:00Z", "account_name": "Acc 77", "currency": "USD", "amount": 280.35, "payment_id": "P-1"}])

    def test_sheet_script_formats_dates_and_sorts_accounts(self):
        script = (Path(__file__).resolve().parents[1] / "google_sheets_webhook.gs").read_text(encoding="utf-8")
        self.assertIn("'dd/MM'", script)
        self.assertIn("column: 2, ascending: true", script)
        self.assertIn("const COLUMNS = ['Ngày', 'Account name', 'Currency', 'Amount', 'Payment ID']", script)


    def test_sheet_script_includes_protected_mobile_snapshot(self):
        script = (Path(__file__).resolve().parents[1] / "google_sheets_webhook.gs").read_text(encoding="utf-8")
        self.assertIn("MOBILE_INBOX_SHEET", script)
        self.assertIn("mobile_snapshot", script)
        self.assertIn("mobileUnlock", script)
        self.assertIn("mobile_revoke_devices", script)


if __name__ == "__main__":
    unittest.main()
