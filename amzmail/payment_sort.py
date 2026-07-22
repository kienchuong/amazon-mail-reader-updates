from __future__ import annotations

import re


_NUMBER_PART = re.compile(r"(\d+)")


def _value(row, key: str, default=""):
    try:
        value = row[key]
    except (KeyError, IndexError, TypeError):
        value = default
    return default if value is None else value


def natural_account_key(row) -> tuple:
    name = str(_value(row, "account_name")).casefold()
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part)
        for part in _NUMBER_PART.split(name)
        if part
    )


def sort_payments(payments) -> list:
    """Sort account names naturally, then show each account's newest payment first."""
    rows = list(payments)
    rows.sort(key=lambda row: str(_value(row, "payment_id")))
    rows.sort(
        key=lambda row: str(_value(row, "mail_date") or _value(row, "first_seen_at")),
        reverse=True,
    )
    rows.sort(key=natural_account_key)
    return rows
