"""Receipt upload and CRUD routes."""

from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, Response
from sqlmodel import Session, select

from financial_tracker_api.config import get_settings
from financial_tracker_api.db import get_session
from financial_tracker_api.deps import get_current_user
from financial_tracker_api.models import LineItem, Receipt, Store, User
from financial_tracker_api.rate_limit import limiter
from financial_tracker_api.schemas import (
    LineItemResponse,
    LineItemUpdateRequest,
    ReceiptResponse,
    ReceiptUpdateRequest,
    StoreResponse,
)
from financial_tracker_api.services.categories import classify_category
from financial_tracker_api.services.flagging import apply_review_flags
from financial_tracker_api.services.ocr import run_ocr
from financial_tracker_api.services.parser import parse_receipt_text
from financial_tracker_api.services.stores import find_or_create_store
from financial_tracker_api.services.tax import classify_tax_status, compute_tax_cents
from financial_tracker_api.services.uploads import (
    delete_receipt_image,
    resolve_receipt_path,
    sniff_image_extension,
)

router = APIRouter(prefix="/api/receipts", tags=["receipts"])

_CHUNK = 64 * 1024


def _store_response(store: Store | None) -> StoreResponse | None:
    if store is None or store.id is None:
        return None
    return StoreResponse(
        id=store.id,
        name=store.name,
        address=store.address,
        phone=store.phone,
    )


def _receipt_response(
    receipt: Receipt, items: list[LineItem], store: Store | None = None
) -> ReceiptResponse:
    store = store if store is not None else receipt.store
    return ReceiptResponse(
        id=receipt.id or 0,
        store_id=receipt.store_id,
        store_name=receipt.store_name or (store.name if store else ""),
        store=_store_response(store),
        purchased_at=receipt.purchased_at,
        subtotal_cents=receipt.subtotal_cents,
        tax_total_cents=receipt.tax_total_cents,
        total_cents=receipt.total_cents,
        needs_review=receipt.needs_review,
        review_reasons=list(receipt.review_reasons or []),
        has_image=bool(receipt.image_path),
        created_at=receipt.created_at,
        line_items=[
            LineItemResponse(
                id=item.id or 0,
                name=item.name,
                quantity=item.quantity,
                quantity_unit=item.quantity_unit or "ea",  # type: ignore[arg-type]
                unit_price_cents=item.unit_price_cents,
                line_total_cents=item.line_total_cents,
                category=item.category,
                tax_status=item.tax_status,  # type: ignore[arg-type]
                tax_amount_cents=item.tax_amount_cents,
                confidence=item.confidence,
                needs_review=item.needs_review,
            )
            for item in items
        ],
    )


def _replace_line_items(
    session: Session,
    receipt: Receipt,
    parsed_lines,
    ocr_confidence: float,
) -> list[LineItem]:
    existing = session.exec(select(LineItem).where(LineItem.receipt_id == receipt.id)).all()
    for item in existing:
        session.delete(item)
    session.commit()

    line_items: list[LineItem] = []
    for parsed_line in parsed_lines:
        category, cat_review = classify_category(parsed_line.name, parsed_line.category)
        tax_status = classify_tax_status(parsed_line.name, category)
        tax_cents = compute_tax_cents(parsed_line.line_total_cents, tax_status)
        item = LineItem(
            receipt_id=receipt.id or 0,
            name=parsed_line.name,
            quantity=parsed_line.quantity,
            quantity_unit=parsed_line.quantity_unit or "ea",
            unit_price_cents=parsed_line.unit_price_cents,
            line_total_cents=parsed_line.line_total_cents,
            category=category,
            tax_status=tax_status,
            tax_amount_cents=tax_cents,
            confidence=min(parsed_line.confidence, ocr_confidence or parsed_line.confidence),
            needs_review=cat_review or tax_status == "unknown",
        )
        line_items.append(item)
        session.add(item)
    apply_review_flags(receipt, line_items, ocr_confidence)
    session.add(receipt)
    session.commit()
    for item in line_items:
        session.refresh(item)
    session.refresh(receipt)
    return line_items


async def _read_upload_limited(file: UploadFile, max_bytes: int) -> bytes:
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File too large")
        chunks.append(chunk)
    return b"".join(chunks)


@router.post("/upload", response_model=ReceiptResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("20/minute")
async def upload_receipt(
    request: Request,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ReceiptResponse:
    """Upload an image, OCR/parse it, and persist receipt + lines."""
    settings = get_settings()
    assert user.id is not None
    content = await _read_upload_limited(file, settings.max_upload_bytes)
    try:
        extension = sniff_image_extension(content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    user_dir = settings.receipts_dir / str(user.id)
    user_dir.mkdir(parents=True, exist_ok=True)
    dest = user_dir / f"{uuid4().hex}{extension}"
    dest.write_bytes(content)

    try:
        ocr_text, ocr_confidence = run_ocr(dest)
    except (OSError, TypeError, ValueError) as exc:
        dest.unlink(missing_ok=True)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not read that image: {exc}",
        ) from exc
    parsed = parse_receipt_text(ocr_text)
    store = find_or_create_store(
        session,
        user_id=user.id,
        name=parsed.store_name,
        address=parsed.store_address,
        phone=parsed.store_phone,
    )

    receipt = Receipt(
        user_id=user.id,
        store_id=store.id if store else None,
        image_path=str(dest.relative_to(settings.data_dir)),
        store_name=store.name if store else parsed.store_name,
        purchased_at=parsed.purchased_at,
        subtotal_cents=parsed.subtotal_cents,
        tax_total_cents=parsed.tax_total_cents,
        total_cents=parsed.total_cents,
        raw_ocr_text=ocr_text,
    )
    session.add(receipt)
    session.commit()
    session.refresh(receipt)

    line_items = _replace_line_items(session, receipt, parsed.lines, ocr_confidence)
    return _receipt_response(receipt, line_items, store)


@router.get("", response_model=list[ReceiptResponse])
def list_receipts(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> list[ReceiptResponse]:
    """List the current user's receipts, newest first."""
    assert user.id is not None
    receipts = session.exec(
        select(Receipt).where(Receipt.user_id == user.id).order_by(Receipt.created_at.desc())
    ).all()
    result: list[ReceiptResponse] = []
    for receipt in receipts:
        items = session.exec(select(LineItem).where(LineItem.receipt_id == receipt.id)).all()
        store = session.get(Store, receipt.store_id) if receipt.store_id else None
        result.append(_receipt_response(receipt, list(items), store))
    return result


@router.get("/{receipt_id}", response_model=ReceiptResponse)
def get_receipt(
    receipt_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ReceiptResponse:
    """Get one receipt owned by the current user."""
    assert user.id is not None
    receipt = session.exec(
        select(Receipt).where(Receipt.id == receipt_id, Receipt.user_id == user.id)
    ).first()
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")
    items = session.exec(select(LineItem).where(LineItem.receipt_id == receipt.id)).all()
    store = session.get(Store, receipt.store_id) if receipt.store_id else None
    return _receipt_response(receipt, list(items), store)


@router.get("/{receipt_id}/image")
def get_receipt_image(
    receipt_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> FileResponse:
    """Serve the receipt image for the owner only."""
    assert user.id is not None
    receipt = session.exec(
        select(Receipt).where(Receipt.id == receipt_id, Receipt.user_id == user.id)
    ).first()
    if receipt is None or not receipt.image_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    settings = get_settings()
    try:
        path = resolve_receipt_path(settings.data_dir, receipt.image_path)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Image not found"
        ) from exc
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    media = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(path.suffix.lower(), "application/octet-stream")
    return FileResponse(path, media_type=media)


@router.post("/{receipt_id}/reparse", response_model=ReceiptResponse)
@limiter.limit("10/minute")
def reparse_receipt(
    request: Request,
    receipt_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ReceiptResponse:
    """Re-run OCR + parse on the stored image and replace line items."""
    assert user.id is not None
    receipt = session.exec(
        select(Receipt).where(Receipt.id == receipt_id, Receipt.user_id == user.id)
    ).first()
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")
    settings = get_settings()
    try:
        path = resolve_receipt_path(settings.data_dir, receipt.image_path)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Image not found"
        ) from exc
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    try:
        ocr_text, ocr_confidence = run_ocr(path)
    except (OSError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Could not read that image: {exc}",
        ) from exc
    parsed = parse_receipt_text(ocr_text)
    store = find_or_create_store(
        session,
        user_id=user.id,
        name=parsed.store_name,
        address=parsed.store_address,
        phone=parsed.store_phone,
    )
    receipt.store_id = store.id if store else None
    receipt.store_name = store.name if store else parsed.store_name
    receipt.purchased_at = parsed.purchased_at
    receipt.subtotal_cents = parsed.subtotal_cents
    receipt.tax_total_cents = parsed.tax_total_cents
    receipt.total_cents = parsed.total_cents
    receipt.raw_ocr_text = ocr_text
    session.add(receipt)
    session.commit()
    session.refresh(receipt)
    line_items = _replace_line_items(session, receipt, parsed.lines, ocr_confidence)
    return _receipt_response(receipt, line_items, store)


@router.delete("/{receipt_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_receipt(
    receipt_id: int,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> Response:
    """Delete a receipt, its line items, and stored image for the owner."""
    assert user.id is not None
    receipt = session.exec(
        select(Receipt).where(Receipt.id == receipt_id, Receipt.user_id == user.id)
    ).first()
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")
    settings = get_settings()
    image_path = receipt.image_path
    items = session.exec(select(LineItem).where(LineItem.receipt_id == receipt.id)).all()
    for item in items:
        session.delete(item)
    session.delete(receipt)
    session.commit()
    delete_receipt_image(settings.data_dir, image_path)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{receipt_id}", response_model=ReceiptResponse)
def patch_receipt(
    receipt_id: int,
    body: ReceiptUpdateRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> ReceiptResponse:
    """Update receipt header fields for the owner."""
    assert user.id is not None
    receipt = session.exec(
        select(Receipt).where(Receipt.id == receipt_id, Receipt.user_id == user.id)
    ).first()
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Receipt not found")
    if body.store_name is not None:
        receipt.store_name = body.store_name
    if body.purchased_at is not None:
        receipt.purchased_at = body.purchased_at
    if body.needs_review is not None:
        receipt.needs_review = body.needs_review
    if body.review_reasons is not None:
        receipt.review_reasons = body.review_reasons
    session.add(receipt)
    session.commit()
    session.refresh(receipt)
    items = session.exec(select(LineItem).where(LineItem.receipt_id == receipt.id)).all()
    store = session.get(Store, receipt.store_id) if receipt.store_id else None
    return _receipt_response(receipt, list(items), store)


@router.patch("/line-items/{item_id}", response_model=LineItemResponse)
def patch_line_item(
    item_id: int,
    body: LineItemUpdateRequest,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> LineItemResponse:
    """Update a line item if its receipt belongs to the current user."""
    assert user.id is not None
    item = session.get(LineItem, item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Line item not found")
    receipt = session.exec(
        select(Receipt).where(Receipt.id == item.receipt_id, Receipt.user_id == user.id)
    ).first()
    if receipt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Line item not found")

    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(item, key, value)
    session.add(item)
    session.commit()
    session.refresh(item)
    return LineItemResponse(
        id=item.id or 0,
        name=item.name,
        quantity=item.quantity,
        quantity_unit=item.quantity_unit or "ea",  # type: ignore[arg-type]
        unit_price_cents=item.unit_price_cents,
        line_total_cents=item.line_total_cents,
        category=item.category,
        tax_status=item.tax_status,  # type: ignore[arg-type]
        tax_amount_cents=item.tax_amount_cents,
        confidence=item.confidence,
        needs_review=item.needs_review,
    )
