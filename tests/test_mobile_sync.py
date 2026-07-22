import unittest

from amzmail.mobile_sync import MAX_BODY_CHARACTERS, build_mobile_snapshot


class MobileSyncTests(unittest.TestCase):
    def test_snapshot_contains_current_message_details_and_payments(self):
        messages = [{
            "account_id": 7, "folder": "INBOX", "uid": "101", "mail_date": "2026-07-20T14:19:00Z",
            "account_name": "Acc 77", "account_email": "acc@example.com", "from_addr": "amazon@example.com",
            "subject": "Remittance Advice", "category": "Payment", "priority": "Normal",
            "trusted_sender": 1, "currency": "USD", "amount": 280.35, "payment_id": "P-1", "snippet": "Payment",
        }]
        snapshot = build_mobile_snapshot(messages, messages, 7, lambda _row: "Full body")
        self.assertEqual(snapshot["action"], "mobile_snapshot")
        self.assertEqual(snapshot["range_days"], 7)
        self.assertEqual(snapshot["messages"][0]["source_id"], "7:INBOX:101")
        self.assertEqual(snapshot["messages"][0]["body"], "Full body")
        self.assertEqual(snapshot["payments"][0]["currency"], "USD")

    def test_body_failure_and_large_body_do_not_stop_snapshot(self):
        messages = [{"account_id": 1, "folder": "INBOX", "uid": "2", "category": "Security", "priority": "High"}]
        failed = build_mobile_snapshot(messages, [], 7, lambda _row: (_ for _ in ()).throw(RuntimeError("offline")))
        self.assertEqual(failed["messages"][0]["body_status"], "error")
        self.assertIn("offline", failed["messages"][0]["body_error"])
        large = build_mobile_snapshot(messages, [], 7, lambda _row: "x" * (MAX_BODY_CHARACTERS + 4))
        self.assertEqual(large["messages"][0]["body_status"], "truncated")
        self.assertEqual(len(large["messages"][0]["body"]), MAX_BODY_CHARACTERS)


    def test_metadata_snapshot_does_not_wait_for_mail_bodies(self):
        messages = [{"account_id": 1, "folder": "INBOX", "uid": "2", "subject": "New mail"}]
        snapshot = build_mobile_snapshot(messages, [], 7)
        self.assertEqual(snapshot["messages"][0]["body_status"], "pending")
        self.assertEqual(snapshot["messages"][0]["body"], "")


if __name__ == "__main__":
    unittest.main()
