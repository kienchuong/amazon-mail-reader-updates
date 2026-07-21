from __future__ import annotations

import base64
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass

from .classifier import classify, extract_payment, looks_interesting, make_snippet
from .imap_reader import ScanResult, _html_to_text
from .microsoft_graph import _OAuthCallback, _callback_handler, _open_microsoft_login


GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GMAIL_ROOT = "https://gmail.googleapis.com/gmail/v1/users/me"
USERINFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"
SCOPES = "openid email https://www.googleapis.com/auth/gmail.readonly"


class GoogleAuthError(RuntimeError):
    pass


@dataclass
class GoogleLogin:
    profile: dict[str, str]
    token_json: str


def _post_form(fields: dict[str, str]) -> dict:
    request = urllib.request.Request(
        GOOGLE_TOKEN,
        data=urllib.parse.urlencode(fields).encode("utf-8"),
        headers={"Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            message = json.loads(detail).get("error_description") or detail
        except json.JSONDecodeError:
            message = detail
        raise GoogleAuthError(f"Google từ chối đăng nhập: {message[:300]}") from exc
    except OSError as exc:
        raise GoogleAuthError(f"Không kết nối được Google: {exc}") from exc


def _get(url: str, access_token: str) -> dict:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code == 401:
            raise GoogleAuthError("Quyền Google đã hết hiệu lực. Hãy đăng nhập Google lại.") from exc
        try:
            message = json.loads(detail).get("error", {}).get("message", detail)
        except json.JSONDecodeError:
            message = detail
        raise GoogleAuthError(f"Gmail API trả lỗi {exc.code}: {message[:300]}") from exc
    except OSError as exc:
        raise GoogleAuthError(f"Không đọc được mail từ Google: {exc}") from exc


def interactive_google_login(client_id: str, client_secret: str, timeout_seconds: int = 300) -> GoogleLogin:
    client_id = client_id.strip()
    client_secret = client_secret.strip()
    if not client_id:
        raise GoogleAuthError("Chưa cấu hình Google Client ID.")
    if not client_secret:
        raise GoogleAuthError("Chưa cấu hình Google Client secret.")
    from http.server import HTTPServer

    callback = _OAuthCallback()
    server = HTTPServer(("127.0.0.1", 0), _callback_handler(callback))
    redirect_uri = f"http://localhost:{server.server_address[1]}"
    state = secrets.token_urlsafe(24)
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': SCOPES,
        'state': state,
        'access_type': 'offline',
        'prompt': 'select_account consent',
    }
    auth_url = f"{GOOGLE_AUTH}?{urllib.parse.urlencode(params)}"
    server.timeout = 1
    try:
        _open_microsoft_login(auth_url)
        deadline = time.monotonic() + timeout_seconds
        while not callback.event.is_set() and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    if not callback.event.is_set():
        raise GoogleAuthError("Đăng nhập quá thời gian 5 phút. Hãy thử lại.")
    if callback.params.get("state") != state:
        raise GoogleAuthError("Kết quả đăng nhập Google không hợp lệ.")
    if "error" in callback.params:
        raise GoogleAuthError(callback.params.get("error_description") or callback.params["error"])
    code = callback.params.get("code")
    if not code:
        raise GoogleAuthError("Google không trả về mã đăng nhập.")
    token = _post_form({
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    })
    if "access_token" not in token or "refresh_token" not in token:
        raise GoogleAuthError("Google không cấp refresh token. Hãy đăng nhập lại.")
    token["expires_at"] = int(time.time()) + int(token.get("expires_in", 3600))
    profile_raw = _get(USERINFO_URL, token["access_token"])
    email = str(profile_raw.get("email") or "")
    if not email:
        raise GoogleAuthError("Không xác định được địa chỉ Gmail.")
    profile = {"id": str(profile_raw.get("sub") or email), "email": email, "display_name": str(profile_raw.get("name") or "")}
    return GoogleLogin(profile, json.dumps(token, separators=(",", ":")))


def _access_token(account, db, client_id: str, client_secret: str) -> str:
    try:
        token = json.loads(db.account_token(account))
    except (ValueError, json.JSONDecodeError) as exc:
        raise GoogleAuthError("Token Google bị lỗi. Hãy đăng nhập Google lại.") from exc
    if token.get("access_token") and int(token.get("expires_at", 0)) > int(time.time()) + 120:
        return token["access_token"]
    refresh_token = token.get("refresh_token")
    if not refresh_token:
        raise GoogleAuthError("Không có quyền làm mới Google. Hãy đăng nhập lại.")
    refreshed = _post_form({"client_id": client_id, "client_secret": client_secret, "refresh_token": refresh_token, "grant_type": "refresh_token"})
    if "access_token" not in refreshed:
        raise GoogleAuthError("Không làm mới được quyền Google. Hãy đăng nhập lại.")
    refreshed["refresh_token"] = refreshed.get("refresh_token") or refresh_token
    refreshed["expires_at"] = int(time.time()) + int(refreshed.get("expires_in", 3600))
    db.update_oauth_token(int(account["id"]), json.dumps(refreshed, separators=(",", ":")))
    return refreshed["access_token"]


def _headers(payload: dict) -> dict[str, str]:
    return {str(item.get("name", "")).lower(): str(item.get("value", "")) for item in payload.get("headers") or []}


def _body_text(payload: dict) -> str:
    parts = payload.get("parts") or []
    if parts:
        values = [_body_text(part) for part in parts]
        return "\n\n".join(value for value in values if value)
    data = ((payload.get("body") or {}).get("data") or "")
    if not data:
        return ""
    raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")
    return _html_to_text(raw) if payload.get("mimeType") == "text/html" else raw


def _message(account, db, client_id: str, client_secret: str, message_id: str, fmt: str) -> dict:
    token = _access_token(account, db, client_id, client_secret)
    return _get(f"{GMAIL_ROOT}/messages/{urllib.parse.quote(message_id, safe='')}?format={fmt}", token)


def fetch_google_body(account, db, client_id: str, client_secret: str, message_id: str) -> str:
    return _body_text(_message(account, db, client_id, client_secret, message_id, "full").get("payload") or {})


def test_google_connection(account, db, client_id: str, client_secret: str) -> None:
    _get(f"{GMAIL_ROOT}/profile", _access_token(account, db, client_id, client_secret))
    db.set_connection_status(int(account["id"]), "Đã kết nối")


def scan_google_account(account, db, client_id: str, client_secret: str, days_back: int, max_messages: int, include_general: bool) -> ScanResult:
    scanned = saved = 0
    try:
        token = _access_token(account, db, client_id, client_secret)
        query = urllib.parse.urlencode({"q": f"newer_than:{max(days_back, 1)}d", "maxResults": min(max(max_messages, 1), 500)})
        listing = _get(f"{GMAIL_ROOT}/messages?{query}", token)
        for item in listing.get("messages") or []:
            message_id = str(item.get("id") or "")
            if not message_id:
                continue
            metadata = _message(account, db, client_id, client_secret, message_id, "metadata")
            headers = _headers(metadata.get("payload") or {})
            from_addr = headers.get("from", "")
            subject = headers.get("subject", "")
            if not include_general and not looks_interesting(from_addr, subject):
                continue
            scanned += 1
            full = _message(account, db, client_id, client_secret, message_id, "full")
            body_text = _body_text(full.get("payload") or {})
            final = classify(from_addr, subject, body_text)
            if final.category == "General" and not include_general:
                continue
            currency = amount = payment_id = None
            if final.category == "Payment":
                currency, amount, payment_id = extract_payment(f"{subject}\n{body_text}")
            internal_date = str(full.get("internalDate") or "")
            mail_date = ""
            if internal_date.isdigit():
                from datetime import datetime, timezone
                mail_date = datetime.fromtimestamp(int(internal_date) / 1000, tz=timezone.utc).isoformat()
            db.upsert_message({
                "account_id": account["id"], "folder": "inbox", "uid": message_id,
                "message_id": headers.get("message-id", ""), "mail_date": mail_date,
                "from_addr": from_addr, "to_addr": headers.get("to", ""), "subject": subject,
                "category": final.category, "priority": final.priority, "trusted_sender": final.trusted_sender,
                "currency": currency, "amount": amount, "payment_id": payment_id,
                "snippet": make_snippet(body_text or subject),
            })
            saved += 1
        db.set_connection_status(int(account["id"]), "Đã kết nối")
        return ScanResult(account["name"], scanned, saved)
    except Exception as exc:
        status = "Cần đăng nhập Google lại" if "đăng nhập" in str(exc).lower() else "Lỗi kết nối"
        db.set_connection_status(int(account["id"]), status)
        return ScanResult(account["name"], scanned, saved, str(exc))
