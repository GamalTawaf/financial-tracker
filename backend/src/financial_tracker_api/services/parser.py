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
    # Costco slips print N (not taxed) / Y (taxed); None = infer later.
    tax_status: str | None = None


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
_DATE = re.compile(r"\b(\d{4}[-/]\d{1,2}[-/]\d{1,2}|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})\b")
_TRAILING_PRICE = re.compile(r"^(?P<name>.+?)\s+(?P<price>\$?-?\d+[.,]\d{2})\s*$")
_WEIGHT_LINE = re.compile(
    r"^(?P<qty>\d+(?:[.,]\d+)?)\s*(?P<qunit>kg|lb|lbs|g|oz)\s*@"
    r"\s*\$?(?P<unit>\d+[.,]\d{2})\s*/\s*(?P=qunit)"
    r"(?:\s+(?P<price>\$?-?\d+[.,]\d{2}))?\s*$",
    re.I,
)
# Count × unit price, e.g. ``2 @ $1.89 3.78`` (Adonis bakery).
_COUNT_AT_PRICE = re.compile(
    r"^(?P<qty>\d+)\s*@\s*\$?(?P<unit>\d+[.,]\d{2})"
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
    r"^(sub\s*tot|subtotal|tot\s*al|total|tax|hst|gst|pst|change|cash|visa|master|"
    r"debit|credit|thank|tel\.?|phone|account|card|trans\.?|date|ref|"
    r"saving|promo|visit|www\.|http|shop |join |how did|your code|"
    r"e&oe|grocery|vegetable|keep |xxx+|#+|mediterranean|"
    r"delivered|cornershop|survey|amount|approved|member|orders|"
    r"chip|whse|trm|trn|opt|items?\s*sold|total\s*tax|total\s*number|"
    r"\(a\)\s*hst|please come|read$)",
    re.I,
)
# Costco warehouse slip: ``57554 BLUEBERRIES 12.99 N`` (SKU + name + price + tax flag).
_COSTCO_ITEM = re.compile(
    r"^(?:(?P<sku>\d{3,})\s+)?(?P<name>.+?)\s+(?P<price>\d+[.,]\d{2})\s+(?P<tax>[NY])\s*$",
    re.I,
)
_COSTCO_PRICE_ONLY = re.compile(r"^(?P<price>\d+[.,]\d{2})\s+(?P<tax>[NY])\s*$", re.I)
_TOTAL_LABEL = re.compile(r"^(sub\s*tot(?:al)?|subtotal|tax|hst|gst|tot(?:al)?)\s*$", re.I)
_MONEY_ONLY = re.compile(r"^\$?\s*-?\d+[.,]\d{2}\s*$")
_SECTION = re.compile(
    r"^(grocery|vegetable|vegetables|produce|fruit|fruits|bakery|meat|deli|"
    r"dairy|beverage|beverages|frozen|seafood|snacks?|"
    r"rfs(?:\s+pr\.?\s*meals?)?|pr\.?\s*meals?|prepared(?:\s+meals?)?)\b",
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
    "rfs": "prepared",
    "pr": "prepared",
    "prepared": "prepared",
}
_STORE_JUNK = re.compile(
    r"^(~+|[-~.=]+|mediterranean\s+market|customer\s+copy)\b",
    re.I,
)
_ITEM_QTY_PREFIX = re.compile(r"^\(\d+\)\s*")
_ADDRESSISH = re.compile(
    r"\b(rd|road|st|street|ave|avenue|blvd|unit|suite|on|qc|bc|ab)\b|\d{3,}",
    re.I,
)


def _costco_tax_status(flag: str | None) -> str | None:
    """Map Costco receipt N/Y flags to our tax_status values."""
    if not flag:
        return None
    return "taxable" if flag.upper() == "Y" else "zero_rated"


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
    name = re.split(r"\s{2,}|:", raw, maxsplit=1)[0].strip(" .:-~")
    name = re.sub(r"\s+", " ", name)
    # Common OCR miss on Adonis receipts.
    name = re.sub(r"\bADONTS\b", "ADONIS", name, flags=re.I)
    return name[:120]


def _clean_item_name(raw: str) -> str:
    """Strip leading ``(2)`` qty markers and trailing junk from product names."""
    name = _ITEM_QTY_PREFIX.sub("", raw).strip(" -.")
    return re.sub(r"\s+", " ", name)


def _pick_store_name(lines: list[str]) -> str:
    """Prefer a real banner (e.g. ADONIS 101204) over OCR crumbs like ``~~``."""
    joined = "\n".join(lines)
    # Costco Orders PDF often puts "Costco" on a later page/header; scan all lines.
    if re.search(r"\bcostco\b|orders\s*&\s*purchases", joined, re.I) or (
        re.search(r"#\d{3,}", joined)
        and re.search(r"\bmember\b", joined, re.I)
        and re.search(r"\b\d+[.,]\d{2}\s+[NY]\b", joined, re.I)
    ):
        warehouse = next(
            (
                re.sub(r"^N\s+", "", line.strip(), flags=re.I)
                for line in lines[:24]
                if re.search(r"#\d{3,}", line) and re.search(r"[A-Za-z]{3,}", line)
            ),
            "",
        )
        if warehouse:
            return _clean_store_name(f"COSTCO {warehouse}")
        return "COSTCO"
    preferred = re.compile(r"\bADON[IT]S\b", re.I)
    for line in lines[:12]:
        if _STORE_JUNK.match(line.strip(" -.")):
            continue
        if preferred.search(line):
            return _clean_store_name(line)
    for line in lines[:8]:
        cleaned = line.strip(" -.~")
        if (
            len(cleaned) >= 3
            and not _STORE_JUNK.match(cleaned)
            and not _ADDRESSISH.search(cleaned)
            and not _PHONE.search(cleaned)
            and not _SECTION.match(cleaned)
            and not _SKIP_NAME.match(cleaned)
            and not _MONEY.search(cleaned)
        ):
            return _clean_store_name(cleaned)
    return _clean_store_name(lines[0])


def _section_category(label: str) -> str | None:
    key = label.lower().strip()
    if key in _SECTION_TO_CATEGORY:
        return _SECTION_TO_CATEGORY[key]
    # Remaining _SECTION matches are RFS / prepared-meal headers.
    return "prepared"


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

    result.store_name = _pick_store_name(lines)
    is_costco = "COSTCO" in result.store_name.upper()
    phone_anywhere = _PHONE.search(text)
    if phone_anywhere:
        result.store_phone = re.sub(r"\s+", " ", phone_anywhere.group(1)).strip()

    address_parts: list[str] = []
    # Address sits under the store banner — skip OCR crumbs / taglines above it.
    header_start = next(
        (
            idx
            for idx, header in enumerate(lines[:16])
            if re.search(r"\bADON[IT]S\b|#\d{3,}", header, re.I)
        ),
        0,
    )
    for header in lines[header_start + 1 : header_start + 8]:
        if _PHONE.search(header) or _STORE_JUNK.match(header.strip(" -.")):
            continue
        if re.match(r"^(member|orders)\b", header, re.I):
            break
        if _SECTION.match(header) or _SKIP_NAME.match(header):
            break
        if _TRAILING_PRICE.match(header) and not _ADDRESSISH.search(header):
            break
        if _COSTCO_ITEM.match(header):
            break
        if _ADDRESSISH.search(header) or re.search(r"[A-Z]\d[A-Z]\s*\d[A-Z]\d", header, re.I):
            address_parts.append(_clean_address_line(header))
            if len([part for part in address_parts if part]) >= 2:
                break
    result.store_address = ", ".join(part for part in address_parts if part)

    pending_name: str | None = None
    pending_total_kind: str | None = None
    section_category: str | None = None
    amount_paid_cents: int | None = None

    for line in lines[1:]:
        date_match = _DATE.search(line)
        if date_match:
            parsed = _parse_date(date_match.group(1))
            if parsed:
                token = date_match.group(1)
                year_part = token.replace("-", "/").split("/")[-1]
                # Prefer purchase timestamps (4-digit year + time) over print headers.
                if result.purchased_at is None or (len(year_part) == 4 and ":" in line):
                    result.purchased_at = parsed

        lower = line.lower()
        section = _SECTION.match(line)
        if section:
            section_category = _section_category(section.group(1))
            pending_name = None
            pending_total_kind = None
            continue

        label = _TOTAL_LABEL.match(line)
        if label and not _MONEY.search(line):
            kind = label.group(1).lower().replace(" ", "")
            if "sub" in kind:
                pending_total_kind = "subtotal"
            elif kind in {"tax", "hst", "gst"}:
                pending_total_kind = "tax"
            else:
                pending_total_kind = "total"
            pending_name = None
            continue

        if pending_total_kind and _MONEY_ONLY.match(line):
            cents = _to_cents(_MONEY.search(line).group(1))  # type: ignore[union-attr]
            if pending_total_kind == "subtotal":
                result.subtotal_cents = cents
            elif pending_total_kind == "tax":
                result.tax_total_cents = cents
            else:
                result.total_cents = cents
            pending_total_kind = None
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
                pending_total_kind = None
                continue
            if "subtot" in compact:
                result.subtotal_cents = cents
                pending_name = None
                pending_total_kind = None
                continue
            if re.search(r"\b(hst|gst|pst|tax)\b", lower) and "hst#" not in lower:
                result.tax_total_cents = cents
                pending_name = None
                pending_total_kind = None
                continue
            # OCR often splits TOTAL → ``TOT AL``; compact still contains ``total``.
            if (
                ("total" in compact or re.search(r"\btot(?:al|\s*al)\b", lower))
                and "sub" not in compact
                and "items" not in lower
                and "saving" not in lower
                and "discount" not in lower
                and "credit" not in lower
                and "account" not in lower
                and "mastercard" not in lower
                and "grocer" not in lower
                and "amount" not in compact
            ):
                result.total_cents = cents
                pending_name = None
                pending_total_kind = None
                continue

        if _SKIP_NAME.match(line):
            if re.match(r"^saving\b", line, re.I):
                pending_name = None
            continue

        costco_item = _COSTCO_ITEM.match(line)
        if costco_item:
            name = _clean_item_name(costco_item.group("name"))
            if len(name) >= 2 and not _SKIP_NAME.match(name):
                price = _to_cents(costco_item.group("price"))
                pending_name = None
                pending_total_kind = None
                result.lines.append(
                    ParsedLine(
                        name=name,
                        quantity=1.0,
                        unit_price_cents=price,
                        line_total_cents=price,
                        confidence=0.95 if is_costco else 0.85,
                        category=section_category,
                        quantity_unit="ea",
                        tax_status=_costco_tax_status(costco_item.group("tax")),
                    )
                )
            continue

        costco_price = _COSTCO_PRICE_ONLY.match(line)
        if costco_price and pending_name:
            price = _to_cents(costco_price.group("price"))
            name = _clean_item_name(pending_name)
            pending_name = None
            pending_total_kind = None
            result.lines.append(
                ParsedLine(
                    name=name,
                    quantity=1.0,
                    unit_price_cents=price,
                    line_total_cents=price,
                    confidence=0.9,
                    category=section_category,
                    quantity_unit="ea",
                    tax_status=_costco_tax_status(costco_price.group("tax")),
                )
            )
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
            name = _clean_item_name(pending_name or "Weighted item")
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

        count_at = _COUNT_AT_PRICE.match(line)
        if count_at:
            qty = float(count_at.group("qty"))
            unit = _to_cents(count_at.group("unit"))
            computed = int(round(qty * unit))
            if count_at.group("price"):
                printed = _to_cents(count_at.group("price"))
                delta = abs(printed - computed)
                # Exact/near match keep printed; small OCR slip → qty×rate; else printed.
                total = computed if 1 < delta <= 15 else printed
            else:
                total = computed
            name = _clean_item_name(pending_name or "Item")
            pending_name = None
            result.lines.append(
                ParsedLine(
                    name=name,
                    quantity=qty,
                    unit_price_cents=unit,
                    line_total_cents=total,
                    confidence=0.9,
                    category=section_category,
                    quantity_unit="ea",
                )
            )
            continue

        priced = _TRAILING_PRICE.match(line)
        if priced:
            name = _clean_item_name(priced.group("name"))
            if len(name) < 2 or _SKIP_NAME.match(name) or _COUNT_AT_PRICE.match(name):
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
            and not re.fullmatch(r"\d{6,}", line)
            and not _MONEY.search(line)
            and not _DATE.search(line)
            and not _ADDRESSISH.search(line)
            and not re.search(r"@|://", line)
            and not _STORE_JUNK.match(line.strip(" -."))
        ):
            pending_name = _clean_item_name(line)

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
