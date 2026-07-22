import unittest
from unittest.mock import patch

from amzmail.supabase_mobile import post_mobile_snapshot


class _Response:
    status = 200

    def read(self):
        return b'{"ok":true}'

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class SupabaseMobileTests(unittest.TestCase):
    @patch("amzmail.supabase_mobile.urllib.request.urlopen", return_value=_Response())
    def test_snapshot_uses_dedicated_secret_header(self, request):
        status, body = post_mobile_snapshot(
            "https://project.supabase.co/functions/v1/mobile-dashboard",
            "sync-secret",
            {"messages": [], "payments": []},
        )
        sent = request.call_args.args[0]
        self.assertEqual(status, 200)
        self.assertEqual(body, '{"ok":true}')
        self.assertEqual(sent.get_header("X-amr-sync-secret"), "sync-secret")
        self.assertEqual(sent.get_method(), "POST")


if __name__ == "__main__":
    unittest.main()
