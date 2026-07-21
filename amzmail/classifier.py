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

AMOUNT_PATTERNS = (
    re.compile(r"(?P<symbol>[$€£¥])\s*(?P<amount>\d[\d,\s]*(?:\.\d{1,2})?)"),
    re.compile(
        r"(?P<currency>USD|EUR|GBP|JPY|CAD|AUD)\s*(?P<amount>\d[\d,\s]*(?:\.\d{1,2})?)",
        re.I,
    ),
    re.compile(
        r"(?P<amount>\d[\d,\s]*(?:\.\d{1,2})?)\s*(?P<currency>USD|EUR|GBP|JPY|CAD|AUD)",
        re.I,
    ),
)

PAYMENT_ID_PATTERN = re.compile(
    r"(payment\s*(id|reference|ref)?|transaction\s*(id|reference))[:\s#-]+([A-Z0-9-]{5,})",
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


def extract_payment(text: str) -> tuple[str | None, float | None, str | None]:
    amount = None
    currency = None
    for pattern in AMOUNT_PATTERNS:
        match = pattern.search(text)
        if not match:
            continue
        raw_amount = match.group("amount").replace(" ", "").replace(",", "")
        try:
            amount = float(raw_amount)
        except ValueError:
            continue
        symbol = match.groupdict().get("symbol")
        currency = match.groupdict().get("currency")
        if symbol:
            currency = CURRENCY_SYMBOLS.get(symbol)
        if currency:
            currency = currency.upper()
        break

    payment_id = None
    id_match = PAYMENT_ID_PATTERN.search(text)
    if id_match:
        payment_id = id_match.group(id_match.lastindex or 0)
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
