from __future__ import annotations

import imaplib
import re
import ssl
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email import policy
from email.parser import BytesParser
from email.utils import parsedate_to_datetime
from html import unescape

from .classifier import classify, extract_payment, looks_interesting, make_snippet


PROVIDER_PRESETS = {
    "Gmail": {"host": "imap.gmail.com", "port": 993, "folder": "INBOX", "use_ssl": True},
    "Outlook": {"host": "outlook.office365.com", "port": 993, "folder": "INBOX", "use_ssl": True},
    "Yahoo": {"host": "imap.mail.yahoo.com", "port": 993, "folder": "INBOX", "use_ssl": True},
    "Custom": {"host": "", "port": 993, "folder": "INBOX", "use_ssl": True},
}


@dataclass
class ScanResult:
    account_name: str
    scanned: int
    saved: int
    error: str | None = None


def _connect(account, password: str):
    if int(account["use_ssl"]):
        ctx = ssl.create_default_context()
        client = imaplib.IMAP4_SSL(account["host"], int(account["port"]), ssl_context=ctx)
    else:
        client = imaplib.IMAP4(account["host"], int(account["port"]))
    client.login(account["username"], password)
    # Read-only SELECT prevents server-side Seen flag changes; all FETCH calls use BODY.PEEK too.
    client.select(account["folder"], readonly=True)
    return client


def test_connection(account, password: str) -> None:
    client = _connect(account, password)
    try:
        client.noop()
    finally:
        _logout(client)


def _logout(client) -> None:
    try:
        client.close()
    except Exception:
        pass
    try:
        client.logout()
    except Exception:
        pass


def _imap_since(days_back: int) -> str:
    since = date.today() - timedelta(days=max(days_back, 1))
    return since.strftime("%d-%b-%Y")


def _fetch_bytes(client, uid: bytes, query: str) -> bytes:
    status, parts = client.uid("fetch", uid, query)
    if status != "OK" or not parts:
        return b""
    chunks = []
    for part in parts:
        if isinstance(part, tuple) and len(part) >= 2 and isinstance(part[1], bytes):
            chunks.append(part[1])
    return b"\n".join(chunks)


def _parse_datetime(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        value = parsedate_to_datetime(raw)
        if value.tzinfo:
            value = value.astimezone()
        return value.isoformat(timespec="seconds")
    except Exception:
        return None


def _html_to_text(html: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", html)
    text = re.sub(r"(?s)<br\s*/?>", "\n", text)
    text = re.sub(r"(?s)</p\s*>", "\n", text)
    text = re.sub(r"(?s)<.*?>", " ", text)
    return unescape(text)


def message_to_text(raw: bytes) -> str:
    if not raw:
        return ""
    msg = BytesParser(policy=policy.default).parsebytes(raw)
    plain_parts: list[str] = []
    html_parts: list[str] = []

    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_disposition() == "attachment":
                continue
            ctype = part.get_content_type()
            if ctype not in ("text/plain", "text/html"):
                continue
            try:
                payload = part.get_content()
            except Exception:
                continue
            if ctype == "text/plain":
                plain_parts.append(str(payload))
            else:
                html_parts.append(_html_to_text(str(payload)))
    else:
        try:
            payload = msg.get_content()
        except Exception:
            payload = ""
        if msg.get_content_type() == "text/html":
            html_parts.append(_html_to_text(str(payload)))
        else:
            plain_parts.append(str(payload))

    return "\n\n".join(plain_parts or html_parts)


def fetch_message_body(account, password: str, uid: str) -> str:
    client = _connect(account, password)
    try:
        raw = _fetch_bytes(client, uid.encode("ascii"), "(BODY.PEEK[])")
        return message_to_text(raw)
    finally:
        _logout(client)


def scan_account(account, password: str, days_back: int, max_messages: int, include_general: bool, db) -> ScanResult:
    client = None
    scanned = 0
    saved = 0
    try:
        client = _connect(account, password)
        status, data = client.uid("search", None, "SINCE", _imap_since(days_back))
        if status != "OK" or not data:
            return ScanResult(account["name"], 0, 0)

        uids = data[0].split()
        if max_messages > 0:
            uids = uids[-max_messages:]

        parser = BytesParser(policy=policy.default)
        for uid in reversed(uids):
            scanned += 1
            header_raw = _fetch_bytes(
                client,
                uid,
                "(BODY.PEEK[HEADER.FIELDS (MESSAGE-ID FROM TO CC DATE SUBJECT)])",
            )
            if not header_raw:
                continue
            header = parser.parsebytes(header_raw)
            from_addr = str(header.get("From", ""))
            subject = str(header.get("Subject", ""))

            if not include_general and not looks_interesting(from_addr, subject):
                continue

            body_text = ""
            preliminary = classify(from_addr, subject)
            if include_general or preliminary.category != "General" or looks_interesting(from_addr, subject):
                full_raw = _fetch_bytes(client, uid, "(BODY.PEEK[])")
                body_text = message_to_text(full_raw)

            final = classify(from_addr, subject, body_text)
            if final.category == "General" and not include_general:
                continue

            currency = amount = payment_id = None
            if final.category == "Payment":
                currency, amount, payment_id = extract_payment(f"{subject}\n{body_text}")

            db.upsert_message(
                {
                    "account_id": account["id"],
                    "folder": account["folder"],
                    "uid": uid.decode("ascii", errors="ignore"),
                    "message_id": str(header.get("Message-ID", "")),
                    "mail_date": _parse_datetime(header.get("Date")),
                    "from_addr": from_addr,
                    "to_addr": str(header.get("To", "")),
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
        return ScanResult(account["name"], scanned, saved)
    except Exception as exc:
        return ScanResult(account["name"], scanned, saved, str(exc))
    finally:
        if client is not None:
            _logout(client)
