from __future__ import annotations

import base64
import hashlib
import json
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

from .classifier import classify, extract_payment, looks_interesting, make_snippet
from .imap_reader import ScanResult, _html_to_text


AUTHORITY = "https://login.microsoftonline.com/common/oauth2/v2.0"
GRAPH_ROOT = "https://graph.microsoft.com/v1.0"
SCOPES = "offline_access User.Read Mail.Read"


class MicrosoftAuthError(RuntimeError):
    pass


@dataclass
class MicrosoftLogin:
    profile: dict[str, str]
    token_json: str


class _OAuthCallback:
    def __init__(self):
        self.params: dict[str, str] = {}
        self.event = threading.Event()


def _callback_handler(state: _OAuthCallback):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 - BaseHTTPRequestHandler API
            query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            state.params = {key: values[0] for key, values in query.items() if values}
            state.event.set()
            body = (
                "<!doctype html><meta charset='utf-8'><title>Amazon Mail Reader</title>"
                "<style>body{font-family:Segoe UI,sans-serif;padding:40px;color:#222}</style>"
                "<h2>Đăng nhập thành công</h2><p>Bạn có thể đóng cửa sổ này và quay lại ứng dụng.</p>"
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format, *_args):
            return

    return Handler


def _post_form(url: str, fields: dict[str, str]) -> dict:
    data = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Accept": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(detail)
            error_value = payload.get("error")
            nested_message = error_value.get("message") if isinstance(error_value, dict) else str(error_value or "")
            message = payload.get("error_description") or nested_message or detail
        except json.JSONDecodeError:
            message = detail
        raise MicrosoftAuthError(f"Microsoft từ chối đăng nhập: {message[:300]}") from exc
    except OSError as exc:
        raise MicrosoftAuthError(f"Không kết nối được Microsoft: {exc}") from exc


def _graph_get(url: str, access_token: str, prefer_text: bool = False) -> dict:
    headers = {"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    if prefer_text:
        headers["Prefer"] = 'outlook.body-content-type="text"'
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        if exc.code == 401:
            raise MicrosoftAuthError("Quyền đăng nhập đã hết hiệu lực. Hãy đăng nhập Microsoft lại.") from exc
        try:
            message = json.loads(detail).get("error", {}).get("message", detail)
        except json.JSONDecodeError:
            message = detail
        raise MicrosoftAuthError(f"Microsoft Graph trả lỗi {exc.code}: {message[:300]}") from exc
    except OSError as exc:
        raise MicrosoftAuthError(f"Không đọc được mail từ Microsoft: {exc}") from exc


def interactive_login(client_id: str, timeout_seconds: int = 300) -> MicrosoftLogin:
    client_id = client_id.strip()
    if not client_id:
        raise MicrosoftAuthError("Chưa cấu hình Microsoft Client ID.")

    callback = _OAuthCallback()
    server = HTTPServer(("127.0.0.1", 0), _callback_handler(callback))
    port = server.server_address[1]
    redirect_uri = f"http://localhost:{port}"
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).rstrip(b"=").decode("ascii")
    state = secrets.token_urlsafe(24)
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "response_mode": "query",
        "scope": SCOPES,
        "state": state,
        "prompt": "select_account",
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{AUTHORITY}/authorize?{urllib.parse.urlencode(params)}"
    server.timeout = 1
    if not webbrowser.open(auth_url, new=1):
        server.server_close()
        raise MicrosoftAuthError("Không mở được trình duyệt mặc định.")
    deadline = time.monotonic() + timeout_seconds
    try:
        while not callback.event.is_set() and time.monotonic() < deadline:
            server.handle_request()
    finally:
        server.server_close()
    if not callback.event.is_set():
        raise MicrosoftAuthError("Đăng nhập quá thời gian 5 phút. Hãy thử lại.")
    if callback.params.get("state") != state:
        raise MicrosoftAuthError("Kết quả đăng nhập không hợp lệ (state không khớp).")
    if "error" in callback.params:
        raise MicrosoftAuthError(callback.params.get("error_description") or callback.params["error"])
    code = callback.params.get("code")
    if not code:
        raise MicrosoftAuthError("Microsoft không trả về mã đăng nhập.")

    token = _post_form(
        f"{AUTHORITY}/token",
        {
            "client_id": client_id,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "code_verifier": verifier,
            "scope": SCOPES,
        },
    )
    if "access_token" not in token or "refresh_token" not in token:
        raise MicrosoftAuthError("Microsoft không cấp đủ quyền dùng lâu dài. Hãy thử đăng nhập lại.")
    token["expires_at"] = int(time.time()) + int(token.get("expires_in", 3600))
    profile_raw = _graph_get(f"{GRAPH_ROOT}/me?$select=id,displayName,mail,userPrincipalName", token["access_token"])
    email = profile_raw.get("mail") or profile_raw.get("userPrincipalName")
    if not email:
        raise MicrosoftAuthError("Không xác định được địa chỉ email Microsoft.")
    profile = {
        "id": str(profile_raw.get("id", "")),
        "display_name": str(profile_raw.get("displayName", "")),
        "email": str(email),
    }
    return MicrosoftLogin(profile, json.dumps(token, separators=(",", ":")))


def _valid_access_token(account, db, client_id: str) -> str:
    latest = db.get_account(int(account["id"]))
    if latest is not None:
        account = latest
    try:
        token = json.loads(db.account_token(account))
    except (ValueError, json.JSONDecodeError) as exc:
        raise MicrosoftAuthError("Token Microsoft bị lỗi. Hãy đăng nhập lại.") from exc
    if token.get("access_token") and int(token.get("expires_at", 0)) > int(time.time()) + 120:
        return token["access_token"]
    refresh_token = token.get("refresh_token")
    if not refresh_token:
        raise MicrosoftAuthError("Không có quyền làm mới. Hãy đăng nhập Microsoft lại.")
    refreshed = _post_form(
        f"{AUTHORITY}/token",
        {
            "client_id": client_id,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "scope": SCOPES,
        },
    )
    if "access_token" not in refreshed:
        raise MicrosoftAuthError("Không làm mới được quyền Microsoft. Hãy đăng nhập lại.")
    refreshed["refresh_token"] = refreshed.get("refresh_token") or refresh_token
    refreshed["expires_at"] = int(time.time()) + int(refreshed.get("expires_in", 3600))
    db.update_oauth_token(int(account["id"]), json.dumps(refreshed, separators=(",", ":")))
    return refreshed["access_token"]


def test_microsoft_connection(account, db, client_id: str) -> None:
    token = _valid_access_token(account, db, client_id)
    _graph_get(f"{GRAPH_ROOT}/me?$select=id", token)
    db.set_connection_status(int(account["id"]), "Đã kết nối")


def _sender(message: dict) -> str:
    item = (message.get("from") or {}).get("emailAddress") or {}
    address = item.get("address", "")
    name = item.get("name", "")
    return f"{name} <{address}>" if name and address else address or name


def _recipients(message: dict) -> str:
    values = []
    for item in message.get("toRecipients") or []:
        address = (item.get("emailAddress") or {}).get("address")
        if address:
            values.append(address)
    return ", ".join(values)


def fetch_microsoft_body(account, db, client_id: str, message_id: str) -> str:
    token = _valid_access_token(account, db, client_id)
    encoded_id = urllib.parse.quote(message_id, safe="")
    payload = _graph_get(f"{GRAPH_ROOT}/me/messages/{encoded_id}?$select=body", token, prefer_text=True)
    body = payload.get("body") or {}
    content = str(body.get("content", ""))
    return _html_to_text(content) if str(body.get("contentType", "")).lower() == "html" else content


def scan_microsoft_account(account, db, client_id: str, days_back: int, max_messages: int, include_general: bool) -> ScanResult:
    scanned = 0
    saved = 0
    try:
        token = _valid_access_token(account, db, client_id)
        top = min(max(max_messages, 1), 100)
        select = "id,internetMessageId,receivedDateTime,from,toRecipients,subject,bodyPreview"
        url = f"{GRAPH_ROOT}/me/mailFolders/inbox/messages?$select={select}&$orderby=receivedDateTime%20desc&$top={top}"
        cutoff = datetime.now(timezone.utc) - timedelta(days=max(days_back, 1))
        done = False
        while url and scanned < max_messages and not done:
            page = _graph_get(url, token, prefer_text=True)
            for message in page.get("value", []):
                if scanned >= max_messages:
                    break
                received = str(message.get("receivedDateTime", ""))
                try:
                    received_dt = datetime.fromisoformat(received.replace("Z", "+00:00"))
                    if received_dt < cutoff:
                        done = True
                        break
                except ValueError:
                    pass
                scanned += 1
                from_addr = _sender(message)
                subject = str(message.get("subject") or "")
                if not include_general and not looks_interesting(from_addr, subject):
                    continue
                body_text = str(message.get("bodyPreview") or "")
                preliminary = classify(from_addr, subject, body_text)
                if preliminary.category != "General" or include_general:
                    body_text = fetch_microsoft_body(account, db, client_id, str(message["id"]))
                final = classify(from_addr, subject, body_text)
                if final.category == "General" and not include_general:
                    continue
                currency = amount = payment_id = None
                if final.category == "Payment":
                    currency, amount, payment_id = extract_payment(f"{subject}\n{body_text}")
                db.upsert_message(
                    {
                        "account_id": account["id"],
                        "folder": "inbox",
                        "uid": str(message["id"]),
                        "message_id": str(message.get("internetMessageId") or ""),
                        "mail_date": received,
                        "from_addr": from_addr,
                        "to_addr": _recipients(message),
                        "subject": subject,
                        "category": final.category,
                        "priority": final.priority,
                        "trusted_sender": final.trusted_sender,
                        "currency": currency,
                        "amount": amount,
                        "payment_id": payment_id,
                        "snippet": make_snippet(body_text or subject),
                    }
                )
                saved += 1
            url = "" if done else str(page.get("@odata.nextLink") or "")
        db.set_connection_status(int(account["id"]), "Đã kết nối")
        return ScanResult(account["name"], scanned, saved)
    except Exception as exc:
        db.set_connection_status(int(account["id"]), "Cần đăng nhập lại" if "đăng nhập lại" in str(exc).lower() else "Lỗi kết nối")
        return ScanResult(account["name"], scanned, saved, str(exc))
