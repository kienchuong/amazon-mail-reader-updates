import unittest

from amzmail.google_sheets import payment_rows
from amzmail.mobile_sync import mobile_payment_rows
from amzmail.payment_sort import sort_payments


class PaymentSortTests(unittest.TestCase):
    def test_account_names_use_case_insensitive_natural_order(self):
        rows = [
            {"account_name": "Acc 10", "mail_date": "2026-07-20T10:00:00Z", "payment_id": "10"},
            {"account_name": "acc 2", "mail_date": "2026-07-20T10:00:00Z", "payment_id": "2"},
            {"account_name": "Acc 1", "mail_date": "2026-07-20T10:00:00Z", "payment_id": "1"},
        ]
        self.assertEqual(
            [row["account_name"] for row in sort_payments(rows)],
            ["Acc 1", "acc 2", "Acc 10"],
        )

    def test_same_account_uses_newest_payment_first(self):
        rows = [
            {"account_name": "Acc 2", "mail_date": "2026-07-19T10:00:00Z", "payment_id": "old"},
            {"account_name": "ACC 2", "mail_date": "2026-07-21T10:00:00Z", "payment_id": "new"},
        ]
        self.assertEqual([row["payment_id"] for row in sort_payments(rows)], ["new", "old"])

    def test_mobile_snapshot_payment_rows_use_shared_order(self):
        rows = [
            {"account_name": "Acc 12", "mail_date": "2026-07-20", "payment_id": "12"},
            {"account_name": "Acc 3", "mail_date": "2026-07-20", "payment_id": "3"},
        ]
        self.assertEqual(
            [row["account_name"] for row in mobile_payment_rows(rows)],
            ["Acc 3", "Acc 12"],
        )

    def test_csv_payment_rows_use_shared_order(self):
        common = {
            "account_email": "account@example.com",
            "currency": "USD",
            "amount": 10,
            "from_addr": "amazon@example.com",
            "subject": "Payment",
            "trusted_sender": 1,
        }
        rows = [
            {**common, "account_name": "Acc 10", "mail_date": "2026-07-20", "payment_id": "10"},
            {**common, "account_name": "Acc 2", "mail_date": "2026-07-20", "payment_id": "2"},
        ]
        self.assertEqual(
            [row["account_name"] for row in payment_rows(rows)],
            ["Acc 2", "Acc 10"],
        )


if __name__ == "__main__":
    unittest.main()
