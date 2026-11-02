"""Receipt review flagging heuristics."""

from __future__ import annotations

from financial_tracker_api.models import LineItem, Receipt


def apply_review_flags(receipt: Receipt, line_items: list[LineItem], ocr_confidence: float) -> None:
    """Mutate receipt/line_items needs_review and review_reasons."""
    reasons: list[str] = []

    if ocr_confidence < 0.55:
        reasons.append("low_ocr_confidence")

    if not line_items:
        reasons.append("no_line_items")

    for item in line_items:
        if item.tax_status == "unknown" or item.confidence < 0.55 or item.needs_review:
            item.needs_review = True
            if "uncertain_line_items" not in reasons:
                reasons.append("uncertain_line_items")

    computed_tax = sum(item.tax_amount_cents for item in line_items)
    if receipt.tax_total_cents is not None and line_items:
        delta = abs(computed_tax - receipt.tax_total_cents)
        if delta > max(25, int(0.15 * receipt.tax_total_cents)):
            reasons.append("tax_total_mismatch")

    computed_lines = sum(item.line_total_cents for item in line_items)
    if receipt.subtotal_cents is not None and line_items:
        delta = abs(computed_lines - receipt.subtotal_cents)
        if delta > max(50, int(0.1 * receipt.subtotal_cents)):
            reasons.append("subtotal_mismatch")

    if not receipt.store_name:
        reasons.append("missing_store")

    receipt.review_reasons = reasons
    receipt.needs_review = bool(reasons)
