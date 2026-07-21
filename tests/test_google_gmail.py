import base64
import unittest

from amzmail.google_gmail import SCOPES, _body_text, _headers


class GoogleGmailTests(unittest.TestCase):
    def test_scope_is_read_only(self):
        self.assertIn("gmail.readonly", SCOPES)
        self.assertNotIn("gmail.modify", SCOPES)
        self.assertNotIn("gmail.send", SCOPES)

    def test_decodes_multipart_html_body(self):
        html = base64.urlsafe_b64encode(b"<p>Payment amount: 280.35</p>").decode().rstrip("=")
        payload = {
            "parts": [
                {"mimeType": "text/html", "body": {"data": html}},
            ]
        }
        self.assertEqual(_body_text(payload).strip(), "Payment amount: 280.35")

    def test_reads_message_headers_case_insensitively(self):
        values = _headers({"headers": [{"name": "From", "value": "Amazon <noreply@example.com>"}]})
        self.assertEqual(values["from"], "Amazon <noreply@example.com>")


if __name__ == "__main__":
    unittest.main()
