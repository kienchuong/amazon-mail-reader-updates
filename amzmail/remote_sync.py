from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, replace
from typing import Any, Protocol


DEFAULT_TIMEOUT_SECONDS = 20
MAX_TIMEOUT_SECONDS = 120


class RemoteSyncError(RuntimeError):
    pass


class RemoteSyncAuthError(RemoteSyncError):
    pass


class RemoteSyncRateLimitError(RemoteSyncError):
    pass


class RemoteSyncTimeoutError(RemoteSyncError):
    pass


class RemoteSyncResponseError(RemoteSyncError):
    pass


class RemoteSyncService(Protocol):
    def post_snapshot(self, snapshot: dict) -> tuple[int, str]: ...


def _timeout(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = DEFAULT_TIMEOUT_SECONDS
    return min(max(parsed, 5), MAX_TIMEOUT_SECONDS)


def _replace_dashboard_api(dashboard_url: str, worker_url: str) -> str:
    if not dashboard_url or not worker_url or "#" not in dashboard_url:
        return dashboard_url
    base, fragment = dashboard_url.split("#", 1)
    values = urllib.parse.parse_qs(fragment, keep_blank_values=True)
    if "api" not in values:
        return dashboard_url
    values["api"] = [worker_url]
    return base + "#" + urllib.parse.urlencode(values, doseq=True)


@dataclass(frozen=True)
class RemoteSyncConfig:
    worker_url: str = ""
    dashboard_url: str = ""
    sync_secret: str = ""
    enabled: bool = True
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS

    @classmethod
    def from_database(cls, db) -> "RemoteSyncConfig":
        worker_url = db.get_setting("cloudflare_mobile_worker_url").strip()
        dashboard_url = db.get_setting("cloudflare_mobile_dashboard_url").strip()
        sync_secret = db.get_secret_setting("cloudflare_mobile_sync_secret").strip()

        # Preserve reusable local configuration without calling the retired
        # Supabase endpoint. The dashboard link and client secret are backend-neutral.
        if not dashboard_url:
            dashboard_url = db.get_setting("supabase_mobile_dashboard_url").strip()
        if not sync_secret:
            sync_secret = db.get_secret_setting("supabase_mobile_sync_secret").strip()

        return cls(
            worker_url=worker_url,
            dashboard_url=_replace_dashboard_api(dashboard_url, worker_url),
            sync_secret=sync_secret,
            enabled=db.get_setting("mobile_auto_sync", "1") == "1",
            timeout_seconds=_timeout(db.get_setting("cloudflare_mobile_timeout_seconds", DEFAULT_TIMEOUT_SECONDS)),
        )

    def normalized(self) -> "RemoteSyncConfig":
        worker_url = self.worker_url.strip().rstrip("/")
        dashboard_url = _replace_dashboard_api(self.dashboard_url.strip(), worker_url)
        return replace(
            self,
            worker_url=worker_url,
            dashboard_url=dashboard_url,
            sync_secret=self.sync_secret.strip(),
            timeout_seconds=_timeout(self.timeout_seconds),
        )

    def save(self, db) -> "RemoteSyncConfig":
        value = self.normalized()
        db.set_setting("cloudflare_mobile_worker_url", value.worker_url)
        db.set_setting("cloudflare_mobile_dashboard_url", value.dashboard_url)
        db.set_secret_setting("cloudflare_mobile_sync_secret", value.sync_secret)
        db.set_setting("cloudflare_mobile_timeout_seconds", str(value.timeout_seconds))
        db.set_setting("mobile_auto_sync", "1" if value.enabled else "0")
        return value


class CloudflareSyncService:
    """Idempotent snapshot client for the Cloudflare Worker API."""

    def __init__(self, config: RemoteSyncConfig, *, retries: int = 1):
        self.config = config.normalized()
        self.retries = max(0, min(int(retries), 2))

    def post_snapshot(self, snapshot: dict) -> tuple[int, str]:
        if not self.config.worker_url:
            raise RemoteSyncError("Chưa cấu hình Cloudflare Worker URL.")
        if not self.config.sync_secret:
            raise RemoteSyncError("Chưa cấu hình Cloudflare Sync Secret.")
        if not isinstance(snapshot.get("messages"), list) or not isinstance(snapshot.get("payments"), list):
            raise RemoteSyncError("Snapshot mobile không hợp lệ.")

        data = json.dumps(snapshot, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            self.config.worker_url,
            data=data,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": "AmazonMailReader/0.6.8",
                "x-amr-sync-secret": self.config.sync_secret,
            },
            method="POST",
        )
        return self._send(request, idempotent=True)

    def health(self) -> dict:
        if not self.config.worker_url:
            raise RemoteSyncError("Chưa cấu hình Cloudflare Worker URL.")
        request = urllib.request.Request(
            self.config.worker_url + "/health",
            headers={"Accept": "application/json", "User-Agent": "AmazonMailReader/0.6.8"},
            method="GET",
        )
        _, body = self._send(request, idempotent=True)
        return json.loads(body)

    def _send(self, request: urllib.request.Request, *, idempotent: bool) -> tuple[int, str]:
        attempts = self.retries + 1 if idempotent else 1
        for attempt in range(attempts):
            try:
                with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                    status = int(response.status)
                    body = response.read().decode("utf-8", errors="replace")
                try:
                    parsed = json.loads(body)
                except json.JSONDecodeError as exc:
                    raise RemoteSyncResponseError("Cloudflare trả về dữ liệu không phải JSON.") from exc
                if not isinstance(parsed, dict):
                    raise RemoteSyncResponseError("Cloudflare trả về JSON không hợp lệ.")
                return status, body
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")[:500]
                if exc.code in {401, 403}:
                    raise RemoteSyncAuthError(f"Cloudflare từ chối xác thực (HTTP {exc.code}).") from exc
                if exc.code == 429:
                    error: RemoteSyncError = RemoteSyncRateLimitError("Cloudflare đang giới hạn yêu cầu (HTTP 429).")
                elif 500 <= exc.code <= 599:
                    error = RemoteSyncError(f"Cloudflare tạm thời lỗi HTTP {exc.code}: {body}")
                else:
                    raise RemoteSyncError(f"Cloudflare trả lỗi HTTP {exc.code}: {body}") from exc
            except (TimeoutError, socket.timeout) as exc:
                error = RemoteSyncTimeoutError(
                    f"Cloudflare không phản hồi trong {self.config.timeout_seconds} giây."
                )
            except urllib.error.URLError as exc:
                if isinstance(exc.reason, (TimeoutError, socket.timeout)):
                    error = RemoteSyncTimeoutError(
                        f"Cloudflare không phản hồi trong {self.config.timeout_seconds} giây."
                    )
                else:
                    error = RemoteSyncError(f"Không kết nối được Cloudflare: {exc.reason}")

            if attempt + 1 >= attempts:
                raise error
            time.sleep(0.5 * (attempt + 1))

        raise RemoteSyncError("Không kết nối được Cloudflare.")
