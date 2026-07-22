from __future__ import annotations

import csv
import json
import urllib.request
from pathlib import Path

from .payment_sort import sort_payments


PAYMENT_COLUMNS = [
    "mail_date",
    "account_name",
    "account_email",
    "currency",
    "amount",
    "payment_id",
    "from_addr",
    "subject",
    "trusted_sender",
]

GOOGLE_SHEET_COLUMNS = [
    "mail_date",
    "account_name",
    "currency",
    "amount",
    "payment_id",
]


def payment_rows(payments) -> list[dict]:
    rows = []
    for row in sort_payments(payments):
        rows.append({column: row[column] for column in PAYMENT_COLUMNS})
    return rows


def google_sheet_rows(payments) -> list[dict]:
    return [
        {column: row[column] for column in GOOGLE_SHEET_COLUMNS}
        for row in sort_payments(payments)
    ]


def export_csv(payments, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=PAYMENT_COLUMNS)
        writer.writeheader()
        for row in payment_rows(payments):
            writer.writerow(row)
    return path


def post_to_google_sheet(webhook_url: str, secret: str, payments) -> tuple[int, str]:
    payload = {
        "secret": secret,
        "rows": google_sheet_rows(payments),
    }
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read().decode("utf-8", errors="replace")
        return response.status, body
