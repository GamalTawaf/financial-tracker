"""Heuristic receipt OCR text parser."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime


@dataclass
class ParsedLine:
    """A single parsed receipt line."""

    name: str
    quantity: float
    unit_price_cents: int
    line_total_cents: int
    confidence: float
    category: str | None = None
    quantity_unit: str = "ea"


@dataclass
class ParsedReceipt:
    """Structured fields extracted from OCR text."""

    store_name: str = ""
    store_address: str = ""
    store_phone: str = ""
    purchased_at: date | None = None
    subtotal_cents: int | None = None
    tax_total_cents: int | None = None
    total_cents: int | None = None
    lines: list[ParsedLine] = field(default_factory=list)


_MONEY = re.compile(r"\$?\s*(-?\d+[.,]\d{2})")
_DATE = re.compile(
    r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b"
)
_TRAILING_PRICE = re.compile(
    r"^(?P<name>.+?)\s+(?P<price>\$?-?\d+[.,]\d{2})\s*$"
)
_WEIGHT_LINE = re.compile(
    r"^(?P<qty>\d+(?:[.,]\d+)?)\s*(?P<qunit>kg|lb|lbs|g|oz)\s*@"
    r"\s*\$?(?P<unit>\d+[.,]\d{2})\s*/\s*(?P=qunit)"
    r"(?:\s+(?P<price>\$?-?\d+[.,]\d{2}))?\s*$",
    re.I,
)
_QTY_UNIT_ALIASES = {
    "kg": "kg",
    "lb": "lb",
    "lbs": "lb",
    "g": "g",
    "oz": "oz",
}
_PHONE = re.compile(r"(?:TEL\.?|PHONE)\s*:?\s*([\d().\-\s]{7,})", re.I)
_SKIP_NAME = re.compile(
    r"^(sub\s*tot|subtotal|total|tax|hst|gst|pst|change|cash|visa|master|"
    r"debit|credit|thank|tel\.?|phone|account|card|trans\.?|date|ref|"
    r"saving|promo|visit|www\.|http|shop |join |how did|your code|"
    r"e&oe|grocery|vegetable|keep |xxx+|#+)",
    re.I,
)
_SECTION = re.compile(
    r"^(grocery|vegetable|vegetables|produce|fruit|fruits|bakery|meat|deli|"
    r"dairy|beverage|beverages|frozen|seafood|snacks?)\b",
    re.I,
)
_SECTION_TO_CATEGORY = {
    "grocery": "grocery",
    "vegetable": "vegetable",
    "vegetables": "vegetable",
    "produce": "vegetable",
    "fruit": "fruit",
    "fruits": "fruit",
    "bakery": "bakery",
    "meat": "meat",
    "deli": "meat",
    "dairy": "dairy",
    "beverage": "beverages",
    "beverages": "beverages",
    "frozen": "grocery",
    "seafood": "meat",
    "snack": "snacks",
    "snacks": "snacks",
}
_ADDRESSISH = re.compile(
    r"\b(rd|road|st|street|ave|avenue|blvd|unit|suite|on|qc|bc|ab)\b|\d{3,}",
    re.I,
)


def _to_cents(raw: str) -> int:
    cleaned = raw.replace("$", "").replace(",", "").strip()
    return int(round(float(cleaned) * 100))


def _parse_date(raw: str, *, today: date | None = None) -> date | None:
    """Parse a date token, preferring the reading closest to *today*.

    Adonis ``Date/Time: 26/10/24`` is year/month/day (2026-10-24), which is
    ambiguous with day/month/year (2024-10-26). Prefer the nearer date.
    """
    cleaned = raw.replace(" ", "")
    formats = (
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%y/%m/%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%m-%d-%Y",
        "%d-%m-%Y",
        "%y-%m-%d",
        "%d/%m/%y",
        "%m/%d/%y",
    )
    candidates: list[date] = []
    for fmt in formats:
        try:
            candidates.append(datetime.strptime(cleaned, fmt).date())
        except ValueError:
            continue
    if not candidates:
        return None
    # Deduplicate while preserving order.
    unique: list[date] = []
    for value in candidates:
        if value not in unique:
            unique.append(value)
    if len(unique) == 1:
        return unique[0]
    anchor = today or date.today()
    return min(unique, key=lambda value: abs((value - anchor).days))


def _clean_store_name(raw: str) -> str:
    # Drop OCR junk after a clear store code / colon.
    name = re.split(r"\s{2,}|:", raw, maxsplit=1)[0].strip(" .:-")
    name = re.sub(r"\s+", " ", name)
    # Common OCR miss on Adonis receipts.
    name = re.sub(r"\bADONTS\b", "ADONIS", name, flags=re.I)
    return name[:120]


def _clean_address_line(raw: str) -> str:
    """Keep street / city / postal; drop trailing OCR noise."""
    line = re.sub(r"\s+", " ", raw).strip(" ,;:")
    # Street lines often end at UNIT <letter> before OCR garbage.
    unit = re.search(r"\b(UNIT|STE|SUITE|#)\s*([A-Z0-9])\b", line, re.I)
    if unit and re.search(r"\b(RD|ROAD|ST|STREET|AVE|BLVD)\b", line, re.I):
        line = line[: unit.end()].strip(" ,;")
    # Cut after a Canadian postal code when present (tolerate O/0 OCR swaps).
    postal = re.search(
        r"([A-Z]\d[A-Z])\s*([O0\d])\s*([A-Z0-9])\s*([A-Z0-9])\b(.*)$",
        line,
        re.I,
    )
    if postal:
        before = line[: postal.start(1)].strip(" ,;")
        second = "0" if postal.group(2).upper() == "O" else postal.group(2)
        code = f"{postal.group(1).upper()} {second}{postal.group(3)}{postal.group(4)}".upper()
        # Common OCR: trailing S for 5.
        code = re.sub(r"([A-Z]\d[A-Z] \d[A-Z])S$", r"\g<1>5", code)
        line = f"{before} {code}".strip() if before else code
    # Keep city / province / street tokens; drop leftover OCR crumbs.
    allowed_short = {
        "ON",
        "QC",
        "BC",
        "AB",
        "MB",
        "SK",
        "NS",
        "NB",
        "PE",
        "NL",
        "YT",
        "NT",
        "NU",
        "RD",
        "ST",
        "AVE",
        "S",
        "N",
        "E",
        "W",
    }
    tokens: list[str] = []
    for token in line.split():
        if re.fullmatch(r"[^\w]+", token):
            continue
        upper = token.upper()
        prev = tokens[-1].upper() if tokens else ""
        unit_letter = prev in {"UNIT", "STE", "SUITE", "#"} and re.fullmatch(r"[A-Z0-9]", upper)
        if (
            len(token) <= 2
            and not re.search(r"\d", token)
            and not unit_letter
            and upper not in allowed_short
        ):
            continue
        tokens.append(token)
    return " ".join(tokens).strip(" ,;")


def parse_receipt_text(text: str) -> ParsedReceipt:
    """Parse OCR text into store, date, totals, and line items."""
    result = ParsedReceipt()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return result

    result.store_name = _clean_store_name(lines[0])
    phone_anywhere = _PHONE.search(text)
    if phone_anywhere:
        result.store_phone = re.sub(r"\s+", " ", phone_anywhere.group(1)).strip()

    address_parts: list[str] = []
    for header in lines[1:8]:
        if _PHONE.search(header):
            continue
        if _SECTION.match(header) or _SKIP_NAME.match(header):
            break
        if _TRAILING_PRICE.match(header) and not _ADDRESSISH.search(header):
            break
        if _ADDRESSISH.search(header) or re.search(r"[A-Z]\d[A-Z]\s*\d[A-Z]\d", header, re.I):
            address_parts.append(_clean_address_line(header))
            if len([part for part in address_parts if part]) >= 2:
                break
    result.store_address = ", ".join(part for part in address_parts if part)

    pending_name: str | None = None
    section_category: str | None = None
    amount_paid_cents: int | None = None

    for line in lines[1:]:
        date_match = _DATE.search(line)
        if date_match and result.purchased_at is None:
            parsed = _parse_date(date_match.group(1))
            if parsed:
                result.purchased_at = parsed

        lower = line.lower()
        section = _SECTION.match(line)
        if section:
            section_category = _SECTION_TO_CATEGORY.get(section.group(1).lower())
            pending_name = None
            continue

        money_match = _MONEY.search(line)
        if money_match:
            cents = _to_cents(money_match.group(1))
            compact = lower.replace(" ", "")
            # Card / tender lines — amount actually charged.
            if re.search(
                r"(mastercard|visa|amex|debit|account\s*:|credit\s*cr)\b",
                lower,
            ):
                amount_paid_cents = cents
                pending_name = None
                continue
            if "subtot" in compact:
                result.subtotal_cents = cents
                pending_name = None
                continue
            if re.search(r"\b(hst|gst|pst|tax)\b", lower) and "hst#" not in lower:
                result.tax_total_cents = cents
                pending_name = None
                continue
            if (
                re.search(r"\btotal\b", lower)
                and "sub" not in lower
                and "items" not in lower
                and "saving" not in lower
                and "discount" not in lower
                and "credit" not in lower
                and "account" not in lower
                and "mastercard" not in lower
            ):
                result.total_cents = cents
                pending_name = None
                continue

        if _SKIP_NAME.match(line):
            if re.match(r"^saving\b", line, re.I):
                pending_name = None
            continue

        weight = _WEIGHT_LINE.match(line)
        if weight:
            qty = float(weight.group("qty").replace(",", "."))
            qty_unit = _QTY_UNIT_ALIASES.get(weight.group("qunit").lower(), "kg")
            unit = _to_cents(weight.group("unit"))
            computed = int(round(qty * unit))
            if weight.group("price"):
                printed = _to_cents(weight.group("price"))
                delta = abs(printed - computed)
                if delta <= 1:
                    # Half-cent rounding (0.085×$11.00 → 93.5¢).
                    total = printed
                elif delta <= 15:
                    # OCR digit slip on the extension (2.71 vs 2.77).
                    total = computed
                else:
                    total = printed
            else:
                total = computed
            name = pending_name or "Weighted item"
            pending_name = None
            result.lines.append(
                ParsedLine(
                    name=name,
                    quantity=qty,
                    unit_price_cents=unit,
                    line_total_cents=total,
                    confidence=0.85,
                    category=section_category,
                    quantity_unit=qty_unit,
                )
            )
            continue

        priced = _TRAILING_PRICE.match(line)
        if priced:
            name = priced.group("name").strip(" -.")
            if len(name) < 2 or _SKIP_NAME.match(name):
                continue
            # Multi-word product name continued from previous bare line.
            if pending_name and not _MONEY.search(pending_name):
                # e.g. P.NUTS&FRUIT then CEDAR FINE COCON 2.99 — keep priced line only.
                pass
            price = _to_cents(priced.group("price"))
            pending_name = None
            result.lines.append(
                ParsedLine(
                    name=name,
                    quantity=1.0,
                    unit_price_cents=price,
                    line_total_cents=price,
                    confidence=0.8,
                    category=section_category,
                    quantity_unit="ea",
                )
            )
            continue

        # Bare product name waiting for a weight/price line.
        if (
            len(line) >= 3
            and not _MONEY.search(line)
            and not _DATE.search(line)
            and not _ADDRESSISH.search(line)
            and not re.search(r"@|://", line)
        ):
            pending_name = line.strip(" -.")

    if result.total_cents is None and result.subtotal_cents is not None:
        result.total_cents = result.subtotal_cents

    _reconcile_totals(result, amount_paid_cents)
    return result


def _reconcile_totals(result: ParsedReceipt, amount_paid_cents: int | None) -> None:
    """Prefer line-sum / card charge when printed TOTAL is clearly wrong.

    Adonis often OCRs ``TOTAL 38.27`` as ``33.27`` while item prices and the
    Mastercard charge still sum to ``38.27``.
    """
    if not result.lines:
        if amount_paid_cents is not None and result.total_cents is None:
            result.total_cents = amount_paid_cents
        return

    lines_sum = sum(line.line_total_cents for line in result.lines)
    paid = amount_paid_cents

    def _near(a: int, b: int, tol: int = 50) -> bool:
        return abs(a - b) <= tol

    # Payment matches the items → trust that over a disagreeing TOTAL line.
    if paid is not None and _near(lines_sum, paid):
        result.total_cents = paid
        if result.tax_total_cents in (None, 0):
            result.subtotal_cents = paid
        return

    if result.total_cents is None:
        result.total_cents = paid if paid is not None else lines_sum
        if result.subtotal_cents is None and result.tax_total_cents in (None, 0):
            result.subtotal_cents = result.total_cents
