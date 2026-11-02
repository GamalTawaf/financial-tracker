"""Spend statistics routes."""

from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from financial_tracker_api.db import get_session
from financial_tracker_api.deps import get_current_user
from financial_tracker_api.models import LineItem, Receipt, User
from financial_tracker_api.schemas import CategoryStatsResponse, CategoryTotal

router = APIRouter(prefix="/api/stats", tags=["stats"])


@router.get("/by-category", response_model=CategoryStatsResponse)
def by_category(
    from_date: date | None = Query(default=None, alias="from"),
    to_date: date | None = Query(default=None, alias="to"),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> CategoryStatsResponse:
    """Roll up line totals by category for the current user."""
    assert user.id is not None
    receipts = session.exec(select(Receipt).where(Receipt.user_id == user.id)).all()
    receipt_ids: list[int] = []
    for receipt in receipts:
        if from_date and receipt.purchased_at and receipt.purchased_at < from_date:
            continue
        if to_date and receipt.purchased_at and receipt.purchased_at > to_date:
            continue
        assert receipt.id is not None
        receipt_ids.append(receipt.id)

    totals: dict[str, CategoryTotal] = {}
    if receipt_ids:
        items = session.exec(select(LineItem).where(LineItem.receipt_id.in_(receipt_ids))).all()
        for item in items:
            bucket = totals.get(item.category)
            if bucket is None:
                bucket = CategoryTotal(
                    category=item.category, total_cents=0, tax_cents=0, item_count=0
                )
                totals[item.category] = bucket
            bucket.total_cents += item.line_total_cents
            bucket.tax_cents += item.tax_amount_cents
            bucket.item_count += 1

    categories = sorted(totals.values(), key=lambda row: row.total_cents, reverse=True)
    return CategoryStatsResponse(from_date=from_date, to_date=to_date, categories=categories)
