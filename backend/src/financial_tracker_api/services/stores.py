"""Find-or-create stores keyed by name + address per user."""

from __future__ import annotations

import re

from sqlmodel import Session, col, select

from financial_tracker_api.models import Receipt, Store

_JUNK_NAME = re.compile(r"^[\W\d_]*$|^(mediterranean\s+market)$", re.I)
_PHONE_DIGITS = re.compile(r"\D+")


def normalize_store_key(value: str, *, fold_zero: bool = False) -> str:
    """Normalize name/address for equality matching.

    Set ``fold_zero`` for addresses so OCR O/0 postal swaps still match; keep
    store codes like ``101204`` intact when matching names.
    """
    cleaned = value.casefold()
    if fold_zero:
        cleaned = cleaned.replace("0", "o")
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def normalize_store_name(name: str) -> str:
    """Clean banner OCR and common merchant misspellings."""
    name = re.sub(r"\s+", " ", (name or "").strip(" .:-~"))
    name = re.sub(r"\bADONTS\b", "ADONIS", name, flags=re.I)
    return name


def normalize_phone(phone: str) -> str:
    """Digits-only phone for matching."""
    return _PHONE_DIGITS.sub("", phone or "")


def _street_core(address_key: str) -> str:
    """Street + city without house number or postal code (OCR-stable)."""
    core = re.sub(r"^\d+\s*", "", address_key)
    core = re.sub(r"\b[a-z]\d[a-z]\s*[o0-9][a-z0-9]{2}\b", "", core)
    return re.sub(r"\s+", " ", core).strip()


def addresses_compatible(a: str, b: str) -> bool:
    """True when addresses are empty, equal, or the same street/city under OCR noise."""
    ka, kb = normalize_store_key(a, fold_zero=True), normalize_store_key(b, fold_zero=True)
    if not ka or not kb:
        return True
    if ka == kb:
        return True
    ca, cb = _street_core(ka), _street_core(kb)
    return bool(ca and cb and (ca == cb or ca in cb or cb in ca))


def is_junk_store_name(name: str) -> bool:
    """Reject OCR crumbs that should never become store records."""
    cleaned = normalize_store_name(name)
    if len(cleaned) < 2:
        return True
    return bool(_JUNK_NAME.match(cleaned))


def _name_keys_match(ka: str, kb: str) -> bool:
    if not ka or not kb:
        return False
    if ka == kb:
        return True
    # "adonis" vs "adonis 101204" — OCR sometimes drops the store code.
    return ka.startswith(f"{kb} ") or kb.startswith(f"{ka} ")


def _stores_match(a: Store, *, name_key: str, address: str, phone: str) -> bool:
    existing_key = normalize_store_key(normalize_store_name(a.name))
    if not _name_keys_match(existing_key, name_key):
        return False
    ka = normalize_store_key(a.address, fold_zero=True)
    kb = normalize_store_key(address, fold_zero=True)
    if ka and kb:
        ca, cb = _street_core(ka), _street_core(kb)
        return bool(ca and cb and (ca == cb or ca in cb or cb in ca))
    phone_a = normalize_phone(a.phone)
    phone_b = normalize_phone(phone)
    if phone_a and phone_b:
        return phone_a == phone_b
    # Same banner with no conflicting street — reuse (phone/address may enrich).
    return True


def _repoint_receipts(session: Session, from_store: Store, to_store: Store | None) -> None:
    for receipt in session.exec(select(Receipt).where(Receipt.store_id == from_store.id)).all():
        receipt.store_id = to_store.id if to_store else None
        if to_store and (not receipt.store_name or is_junk_store_name(receipt.store_name)):
            receipt.store_name = to_store.name
        session.add(receipt)


def _enrich(winner: Store, donor: Store) -> bool:
    dirty = False
    if donor.phone and not winner.phone:
        winner.phone = donor.phone
        dirty = True
    if len(donor.address or "") > len(winner.address or ""):
        winner.address = donor.address
        dirty = True
    if len(normalize_store_name(donor.name)) > len(normalize_store_name(winner.name)):
        winner.name = normalize_store_name(donor.name)[:200]
        dirty = True
    return dirty


def consolidate_stores(session: Session, user_id: int) -> None:
    """Merge near-duplicate stores for a user and re-point receipts."""
    stores = list(session.exec(select(Store).where(Store.user_id == user_id)).all())
    if len(stores) < 2 and not any(is_junk_store_name(s.name) for s in stores):
        return

    keepers: list[Store] = []
    absorbed: list[Store] = []
    for store in sorted(stores, key=lambda s: s.id or 0):
        name_key = normalize_store_key(normalize_store_name(store.name))
        if not name_key or is_junk_store_name(store.name):
            absorbed.append(store)
            continue
        twin = next(
            (
                k
                for k in keepers
                if _stores_match(k, name_key=name_key, address=store.address, phone=store.phone)
            ),
            None,
        )
        if twin is None:
            keepers.append(store)
            continue
        if _enrich(twin, store):
            session.add(twin)
        _repoint_receipts(session, store, twin)
        absorbed.append(store)

    for store in absorbed:
        target = next(
            (
                k
                for k in keepers
                if (
                    normalize_phone(store.phone)
                    and normalize_phone(store.phone) == normalize_phone(k.phone)
                )
                or addresses_compatible(store.address, k.address)
            ),
            None,
        )
        _repoint_receipts(session, store, target)
        session.delete(store)

    if absorbed:
        session.commit()


def find_or_create_store(
    session: Session,
    *,
    user_id: int,
    name: str,
    address: str = "",
    phone: str = "",
) -> Store | None:
    """Return an existing store for this user or create one.

    Matching uses street/city cores (ignoring house-number OCR slips) and phone
    when an address is missing, so 3045 vs 3245 Wonderland stays one Adonis.
    """
    name = normalize_store_name(name)
    address = (address or "").strip()
    phone = (phone or "").strip()
    if not name or is_junk_store_name(name):
        return None

    name_key = normalize_store_key(name)
    existing = session.exec(select(Store).where(Store.user_id == user_id)).all()
    for store in existing:
        if is_junk_store_name(store.name):
            continue
        if not _stores_match(store, name_key=name_key, address=address, phone=phone):
            continue
        dirty = False
        if phone and not store.phone:
            store.phone = phone
            dirty = True
        if address and (
            not store.address
            or (addresses_compatible(store.address, address) and len(address) >= len(store.address))
        ):
            store.address = address
            dirty = True
        if len(name) > len(store.name or ""):
            store.name = name[:200]
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
    """List stores for a user (after consolidating OCR duplicates), name ascending."""
    consolidate_stores(session, user_id)
    return list(
        session.exec(select(Store).where(Store.user_id == user_id).order_by(col(Store.name))).all()
    )
