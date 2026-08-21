from __future__ import annotations

import json
import socket
import sqlite3
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from amzmail.remote_sync import (
    CloudflareSyncService,
    RemoteSyncAuthError,
    RemoteSyncConfig,
    RemoteSyncError,
    RemoteSyncResponseError,
    RemoteSyncTimeoutError,
)


ROOT = Path(__file__).resolve().parent.parent


class FakeDatabase:
    def __init__(self, settings=None, secrets=None):
        self.settings = dict(settings or {})
        self.secrets = dict(secrets or {})

    def get_setting(self, key, default=""):
        return self.settings.get(key, default)

    def set_setting(self, key, value):
        self.settings[key] = value

    def get_secret_setting(self, key, default=""):
        return self.secrets.get(key, default)

    def set_secret_setting(self, key, value):
        self.secrets[key] = value


class Response:
    def __init__(self, status=200, body=b'{"ok":true}'):
        self.status = status
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.body


class RemoteSyncTests(unittest.TestCase):
    def config(self, **values):
        defaults = {
            "worker_url": "https://worker.example.test",
            "dashboard_url": "https://dashboard.example/#api=old&t=token",
            "sync_secret": "sync-secret",
            "enabled": True,
            "timeout_seconds": 20,
        }
        defaults.update(values)
        return RemoteSyncConfig(**defaults)

    def test_post_snapshot_success_and_headers(self):
        service = CloudflareSyncService(self.config(), retries=0)
        with patch("urllib.request.urlopen", return_value=Response()) as opener:
            status, body = service.post_snapshot({"messages": [], "payments": []})
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"ok": True})
        request = opener.call_args.args[0]
        self.assertEqual(request.get_header("X-amr-sync-secret"), "sync-secret")

    def test_auth_error_is_clear_and_not_retried(self):
        error = urllib.error.HTTPError(
            "https://worker.example.test", 401, "Unauthorized", {}, None
        )
        error.read = lambda: b'{"error":"Unauthorized"}'
        with patch("urllib.request.urlopen", side_effect=error) as opener:
            with self.assertRaises(RemoteSyncAuthError):
                CloudflareSyncService(self.config()).post_snapshot({"messages": [], "payments": []})
        self.assertEqual(opener.call_count, 1)

    def test_rate_limit_is_clear_and_retried_once(self):
        error = urllib.error.HTTPError(
            "https://worker.example.test", 429, "Too Many Requests", {}, None
        )
        error.read = lambda: b'{"error":"Rate limited"}'
        with patch("urllib.request.urlopen", side_effect=error) as opener:
            with self.assertRaisesRegex(RemoteSyncError, "giới hạn"):
                CloudflareSyncService(self.config(), retries=1).post_snapshot({"messages": [], "payments": []})
        self.assertEqual(opener.call_count, 2)

    def test_server_error_retries_idempotent_snapshot(self):
        error = urllib.error.HTTPError(
            "https://worker.example.test", 503, "Unavailable", {}, None
        )
        error.read = lambda: b'{"error":"Unavailable"}'
        with patch("urllib.request.urlopen", side_effect=[error, Response()]) as opener:
            status, _ = CloudflareSyncService(self.config(), retries=1).post_snapshot(
                {"messages": [], "payments": []}
            )
        self.assertEqual(status, 200)
        self.assertEqual(opener.call_count, 2)

    def test_timeout_and_network_error_do_not_escape_as_raw_errors(self):
        with patch("urllib.request.urlopen", side_effect=socket.timeout()):
            with self.assertRaises(RemoteSyncTimeoutError):
                CloudflareSyncService(self.config(), retries=0).post_snapshot({"messages": [], "payments": []})
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("dns failed")):
            with self.assertRaisesRegex(RemoteSyncError, "dns failed"):
                CloudflareSyncService(self.config(), retries=0).post_snapshot({"messages": [], "payments": []})

    def test_malformed_response_is_rejected(self):
        with patch("urllib.request.urlopen", return_value=Response(body=b"not-json")):
            with self.assertRaises(RemoteSyncResponseError):
                CloudflareSyncService(self.config(), retries=0).post_snapshot({"messages": [], "payments": []})
        with patch("urllib.request.urlopen", return_value=Response(body=b"")):
            with self.assertRaises(RemoteSyncResponseError):
                CloudflareSyncService(self.config(), retries=0).post_snapshot({"messages": [], "payments": []})

    def test_health_uses_worker_health_endpoint(self):
        with patch(
            "urllib.request.urlopen",
            return_value=Response(body=b'{"ok":true,"database":"connected"}'),
        ) as opener:
            result = CloudflareSyncService(self.config(), retries=0).health()
        self.assertTrue(result["ok"])
        self.assertEqual(opener.call_args.args[0].full_url, "https://worker.example.test/health")

    def test_legacy_secret_is_reused_without_reusing_supabase_endpoint(self):
        db = FakeDatabase(
            settings={
                "supabase_mobile_function_url": "https://old.supabase.co/functions/v1/mobile-dashboard",
                "supabase_mobile_dashboard_url": "https://example.test/#api=old&t=dashboard-token",
            },
            secrets={"supabase_mobile_sync_secret": "legacy-secret"},
        )
        config = RemoteSyncConfig.from_database(db)
        self.assertEqual(config.worker_url, "")
        self.assertEqual(config.sync_secret, "legacy-secret")

        saved = RemoteSyncConfig(
            worker_url="https://worker.example.workers.dev",
            dashboard_url=config.dashboard_url,
            sync_secret=config.sync_secret,
        ).save(db)
        self.assertIn("api=https%3A%2F%2Fworker.example.workers.dev", saved.dashboard_url)
        self.assertEqual(db.settings["cloudflare_mobile_worker_url"], saved.worker_url)

    def test_d1_schema_and_duplicate_upsert(self):
        connection = sqlite3.connect(":memory:")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.executescript((ROOT / "cloudflare" / "migrations" / "0001_initial.sql").read_text("utf-8"))
        statement = """
            INSERT INTO amr_mobile_snapshot
              (id, payload, chunk_count, payload_size_bytes, synced_at)
            VALUES(1, ?, 0, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              payload=excluded.payload,
              chunk_count=excluded.chunk_count,
              payload_size_bytes=excluded.payload_size_bytes,
              synced_at=excluded.synced_at
        """
        first = '{"messages":[],"payments":[]}'
        second = '{"messages":[1],"payments":[]}'
        connection.execute(statement, (first, len(first.encode()), "first"))
        connection.execute(statement, (second, len(second.encode()), "second"))
        row = connection.execute("SELECT COUNT(*), payload, synced_at FROM amr_mobile_snapshot").fetchone()
        self.assertEqual(row, (1, '{"messages":[1],"payments":[]}', "second"))

        connection.execute(
            """
            UPDATE amr_mobile_snapshot
            SET payload=NULL, chunk_count=2, payload_size_bytes=?, synced_at='third'
            WHERE id=1
            """,
            (len(second.encode()),),
        )
        connection.executemany(
            "INSERT INTO amr_mobile_snapshot_chunk(snapshot_id, chunk_index, payload_chunk) VALUES(1, ?, ?)",
            [(0, second[:10]), (1, second[10:])],
        )
        chunks = connection.execute(
            "SELECT payload_chunk FROM amr_mobile_snapshot_chunk WHERE snapshot_id=1 ORDER BY chunk_index"
        ).fetchall()
        self.assertEqual("".join(item[0] for item in chunks), second)
        connection.close()


if __name__ == "__main__":
    unittest.main()
