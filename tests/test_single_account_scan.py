import unittest
from unittest.mock import MagicMock, patch

from amzmail.ui import AmazonMailReaderApp


class SingleAccountScanTests(unittest.TestCase):
    def setUp(self):
        self.app = object.__new__(AmazonMailReaderApp)
        self.app.db = MagicMock()

    def test_dispatches_microsoft_oauth_to_graph_reader(self):
        account = {"id": 1, "auth_type": "microsoft_oauth"}
        with patch("amzmail.ui.scan_microsoft_account", return_value="result") as scanner:
            result = self.app._scan_one_account(account, 7, 300, False, "ms-id", "google-id", "secret")

        self.assertEqual(result, "result")
        scanner.assert_called_once_with(account, self.app.db, "ms-id", 7, 300, False)

    def test_dispatches_google_oauth_to_gmail_reader(self):
        account = {"id": 2, "auth_type": "google_oauth"}
        with patch("amzmail.ui.scan_google_account", return_value="result") as scanner:
            result = self.app._scan_one_account(account, 7, 300, False, "ms-id", "google-id", "secret")

        self.assertEqual(result, "result")
        scanner.assert_called_once_with(account, self.app.db, "google-id", "secret", 7, 300, False)

    def test_dispatches_app_password_account_to_imap_reader(self):
        account = {"id": 3, "auth_type": "imap_password"}
        self.app.db.account_password.return_value = "app-password"
        with patch("amzmail.ui.scan_account", return_value="result") as scanner:
            result = self.app._scan_one_account(account, 7, 300, False, "ms-id", "google-id", "secret")

        self.assertEqual(result, "result")
        scanner.assert_called_once_with(account, "app-password", 7, 300, False, self.app.db)

    def test_inactive_selected_account_can_be_scanned_manually(self):
        account = {"id": 7, "name": "Acc 77", "active": 0}
        self.app.scan_running = False
        self.app.selected_account_id = 7
        self.app.db.get_account.return_value = account
        self.app._start_account_scan = MagicMock()

        self.app.start_selected_account_scan()

        self.app.db.get_account.assert_called_once_with(7)
        self.app._start_account_scan.assert_called_once_with([account], single_account=True)


if __name__ == "__main__":
    unittest.main()
