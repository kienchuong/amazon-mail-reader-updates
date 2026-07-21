from __future__ import annotations

import re
from dataclasses import dataclass
from email.utils import parseaddr


AMAZON_DOMAINS = (
    "amazon.com",
    "amazon.co.uk",
    "amazon.de",
    "amazon.fr",
    "amazon.it",
    "amazon.es",
    "amazon.co.jp",
    "amazonses.com",
)

SECURITY_DOMAINS = (
    "google.com",
    "accounts.google.com",
    "microsoft.com",
    "accountprotection.microsoft.com",
    "live.com",
    "outlook.com",
    "yahoo.com",
    "yahoo-inc.com",
    "yahooinc.com",
    "zoho.com",
    "zohomail.com",
)

PAYMENT_KEYWORDS = (
    "payment",
    "royalty",
    "paid",
    "payout",
    "deposit",
    "disbursement",
)

REJECT_KEYWORDS = (
    "reject",
    "rejected",
    "submission rejected",
    "design rejected",
    "removed",
    "product removed",
    "listing removed",
    "violation",
)

AMAZON_ACCOUNT_KEYWORDS = (
    "action required",
    "account status",
    "account health",
    "tax interview",
    "bank account",
    "charge method",
    "trademark",
    "copyright",
    "intellectual property",
)

SECURITY_URGENT_KEYWORDS = (
    "password was changed",
    "password changed",
    "recovery email changed",
    "phone number changed",
    "account locked",
    "security info was replaced",
)

SECURITY_HIGH_KEYWORDS = (
    "new sign-in",
    "new signin",
    "new login",
    "suspicious activity",
    "unusual activity",
    "two-step verification",
    "2-step verification",
    "two factor",
    "2fa",
    "security alert",
    "new app connected",
    "new application connected",
    "connected to your microsoft account",
    "application connectée",
    "applications connectées",
    "connectée à votre compte",
    "connectées à votre compte",
    "nouvelle application",
    "nouvelles applications",
)

SECURITY_MEDIUM_KEYWORDS = (
    "verification code",
    "security code",
    "one-time code",
    "otp",
    "new device",
)

CURRENCY_SYMBOLS = {
    "$": "USD",
    "€": "EUR",
    "£": "GBP",
    "¥": "JPY",
}

CURRENCY_CODES = "USD|EUR|GBP|JPY|CAD|AUD"
AMOUNT_VALUE = r"\d(?:[\d.,\u00a0 ]*\d)?"

PAYMENT_CURRENCY_PATTERN = re.compile(
    rf"payment\s+currency\s*[:#-]?\s*(?P<currency>{CURRENCY_CODES})\b",
    re.I,
)

PAYMENT_AMOUNT_PATTERN = re.compile(
    rf"payment\s+amount\s*[:#-]?\s*"
    rf"(?:(?P<prefix>[$€£¥]|{CURRENCY_CODES})\s*)?"
    rf"(?P<amount>{AMOUNT_VALUE})"
    rf"(?:\s*(?P<suffix>{CURRENCY_CODES}))?",
    re.I,
)

AMOUNT_PATTERNS = (
    re.compile(rf"(?P<symbol>[$€£¥])\s*(?P<amount>{AMOUNT_VALUE})"),
    re.compile(
        rf"(?P<currency>{CURRENCY_CODES})\s*(?P<amount>{AMOUNT_VALUE})",
        re.I,
    ),
    re.compile(
        rf"(?P<amount>{AMOUNT_VALUE})\s*(?P<currency>{CURRENCY_CODES})",
        re.I,
    ),
)

PAYMENT_ID_PATTERN = re.compile(
    r"(?:payment\s*(?:id|reference|ref|number)|payment\s*#|transaction\s*(?:id|reference))"
    r"\s*[:#-]?\s*(?P<payment_id>[A-Z0-9-]{5,})",
    re.I,
)


@dataclass(frozen=True)
class Classification:
    category: str
    priority: str
    trusted_sender: bool


def _domain(address: str) -> str:
    parsed = parseaddr(address)[1].lower()
    if "@" not in parsed:
        return ""
    return parsed.rsplit("@", 1)[1]


def _domain_matches(domain: str, allowed: tuple[str, ...]) -> bool:
    return any(domain == item or domain.endswith("." + item) for item in allowed)


def classify(from_addr: str, subject: str, body_text: str = "") -> Classification:
    haystack = f"{subject}\n{body_text}".lower()
    haystack = haystack.replace("(s)", "")
    domain = _domain(from_addr)
    is_amazon = _domain_matches(domain, AMAZON_DOMAINS)
    is_security_sender = _domain_matches(domain, SECURITY_DOMAINS)

    if any(k in haystack for k in SECURITY_URGENT_KEYWORDS):
        return Classification("Security", "Urgent", is_security_sender)
    if any(k in haystack for k in SECURITY_HIGH_KEYWORDS):
        return Classification("Security", "High", is_security_sender)
    if any(k in haystack for k in SECURITY_MEDIUM_KEYWORDS):
        return Classification("Security", "Medium", is_security_sender)

    if is_amazon or "amazon" in subject.lower():
        if any(k in haystack for k in PAYMENT_KEYWORDS):
            return Classification("Payment", "Normal", is_amazon)
        if any(k in haystack for k in REJECT_KEYWORDS):
            return Classification("Reject", "High", is_amazon)
        if any(k in haystack for k in AMAZON_ACCOUNT_KEYWORDS):
            return Classification("Amazon Account", "High", is_amazon)
        return Classification("Amazon", "Normal", is_amazon)

    return Classification("General", "Normal", is_security_sender)


def looks_interesting(from_addr: str, subject: str) -> bool:
    lower = subject.lower()
    domain = _domain(from_addr)
    return (
        _domain_matches(domain, AMAZON_DOMAINS)
        or _domain_matches(domain, SECURITY_DOMAINS)
        or "amazon" in lower
        or any(k in lower for k in PAYMENT_KEYWORDS)
        or any(k in lower for k in REJECT_KEYWORDS)
        or any(k in lower for k in SECURITY_URGENT_KEYWORDS)
        or any(k in lower for k in SECURITY_HIGH_KEYWORDS)
        or any(k in lower for k in SECURITY_MEDIUM_KEYWORDS)
    )


def _parse_amount(raw: str) -> float | None:
    value = raw.replace("\u00a0", "").replace(" ", "")
    if not value:
        return None
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value:
        decimals = len(value) - value.rfind(",") - 1
        value = value.replace(",", ".") if decimals in (1, 2) else value.replace(",", "")
    elif value.count(".") > 1:
        parts = value.split(".")
        value = "".join(parts[:-1]) + "." + parts[-1]
    try:
        return float(value)
    except ValueError:
        return None


def _currency_from_token(token: str | None) -> str | None:
    if not token:
        return None
    return CURRENCY_SYMBOLS.get(token, token.upper())


def extract_payment(text: str) -> tuple[str | None, float | None, str | None]:
    currency_match = PAYMENT_CURRENCY_PATTERN.search(text)
    currency = currency_match.group("currency").upper() if currency_match else None

    amount = None
    labelled_amount = PAYMENT_AMOUNT_PATTERN.search(text)
    if labelled_amount:
        amount = _parse_amount(labelled_amount.group("amount"))
        currency = currency or _currency_from_token(
            labelled_amount.group("prefix") or labelled_amount.group("suffix")
        )

    if amount is None:
        currency = None
    for pattern in AMOUNT_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        amount = _parse_amount(match.group("amount"))
        if amount is None:
            continue
        symbol = match.groupdict().get("symbol")
        currency = match.groupdict().get("currency")
        currency = _currency_from_token(symbol or currency)
        break

    payment_id = None
    id_match = PAYMENT_ID_PATTERN.search(text)
    if id_match:
        payment_id = id_match.group("payment_id")
    return currency, amount, payment_id


def make_snippet(text: str, limit: int = 260) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    clean = re.sub(
        r"(?i)(verification|security|one-time|otp)\s*(code)?\s*[:#-]?\s*\d{4,8}",
        r"\1 code: [hidden]",
        clean,
    )
    clean = re.sub(r"\b\d{6,8}\b", "[hidden-code]", clean)
    if len(clean) > limit:
        return clean[: limit - 1].rstrip() + "..."
    return clean
