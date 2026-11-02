"""Find-or-create stores keyed by name + address per user."""

from __future__ import annotations

import re

from sqlmodel import Session, col, select

from financial_tracker_api.models import Store


def normalize_store_key(value: str) -> str:
    """Normalize name/address for equality matching."""
    cleaned = value.casefold()
    cleaned = cleaned.replace("0", "o")  # OCR often swaps O/0 in postal codes
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def find_or_create_store(
    session: Session,
    *,
    user_id: int,
    name: str,
    address: str = "",
    phone: str = "",
) -> Store | None:
    """Return an existing store for this user or create one.

    Matching is on normalized name + address. Empty name yields no store.
    """
    name = (name or "").strip()
    address = (address or "").strip()
    phone = (phone or "").strip()
    if not name:
        return None

    name_key = normalize_store_key(name)
    address_key = normalize_store_key(address)

    existing = session.exec(select(Store).where(Store.user_id == user_id)).all()
    for store in existing:
        if (
            normalize_store_key(store.name) == name_key
            and normalize_store_key(store.address) == address_key
        ):
            # Fill missing details when a later receipt OCR is richer.
            dirty = False
            if phone and not store.phone:
                store.phone = phone
                dirty = True
            if address and len(address) > len(store.address or ""):
                store.address = address
                dirty = True
            if dirty:
                session.add(store)
                session.commit()
                session.refresh(store)
            return store

    store = Store(user_id=user_id, name=name[:200], address=address[:400], phone=phone[:64])
    session.add(store)
    session.commit()
    session.refresh(store)
    return store


def list_stores_for_user(session: Session, user_id: int) -> list[Store]:
    """List stores for a user, name ascending."""
    return list(
        session.exec(
            select(Store).where(Store.user_id == user_id).order_by(col(Store.name))
        ).all()
    )
