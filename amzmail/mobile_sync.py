from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from typing import Callable


MAX_BODY_CHARACTERS = 45000


def _value(row, key: str, default=""):
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        value = default
    return default if value is None else value


def mobile_message_rows(messages, body_loader: Callable) -> list[dict]:
    """Build the current mobile snapshot without persisting mail bodies locally."""
    rows = []
    for message in messages:
        body = ""
        body_error = ""
        try:
            body = body_loader(message) or ""
        except Exception as exc:  # A single unavailable mailbox must not block the snapshot.
            body_error = str(exc)
        truncated = len(body) > MAX_BODY_CHARACTERS
        rows.append(
            {
                "source_id": f"{_value(message, 'account_id')}:{_value(message, 'folder')}:{_value(message, 'uid')}",
                "mail_date": str(_value(message, "mail_date")),
                "account_name": str(_value(message, "account_name")),
                "account_email": str(_value(message, "account_email")),
                "from_addr": str(_value(message, "from_addr")),
                "subject": str(_value(message, "subject")),
                "category": str(_value(message, "category")),
                "priority": str(_value(message, "priority")),
                "trusted_sender": bool(_value(message, "trusted_sender", False)),
                "currency": str(_value(message, "currency")),
                "amount": _value(message, "amount", ""),
                "payment_id": str(_value(message, "payment_id")),
                "snippet": str(_value(message, "snippet")),
                "body": body[:MAX_BODY_CHARACTERS],
                "body_status": "truncated" if truncated else ("error" if body_error else "ok"),
                "body_error": body_error[:500],
            }
        )
    return rows


def mobile_payment_rows(payments) -> list[dict]:
    return [
        {
            "mail_date": str(_value(row, "mail_date")),
            "account_name": str(_value(row, "account_name")),
            "account_email": str(_value(row, "account_email")),
            "currency": str(_value(row, "currency")),
            "amount": _value(row, "amount", ""),
            "payment_id": str(_value(row, "payment_id")),
        }
        for row in payments
    ]


def build_mobile_snapshot(messages, payments, days_back: int, body_loader: Callable) -> dict:
    return {
        "action": "mobile_snapshot",
        "range_days": max(int(days_back), 1),
        "synced_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "messages": mobile_message_rows(messages, body_loader),
        "payments": mobile_payment_rows(payments),
    }


def post_mobile_action(webhook_url: str, secret: str, action: str, **values) -> tuple[int, str]:
    payload = {"secret": secret, "action": action, **values}
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        return response.status, response.read().decode("utf-8", errors="replace")
