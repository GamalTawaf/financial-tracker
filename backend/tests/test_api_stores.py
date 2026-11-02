"""Store list + find-or-create via receipt uploads."""

from helpers import ADONIS_OCR, auth_header, register, upload_receipt
from sqlmodel import Session, select

from financial_tracker_api.models import Store, User


def test_upload_reuses_store_for_same_name_and_address(client) -> None:
    token = register(client, "stores@example.com")
    headers = auth_header(token)

    first = upload_receipt(client, token, ocr_text=ADONIS_OCR)
    second = upload_receipt(client, token, ocr_text=ADONIS_OCR)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["store_id"] == second.json()["store_id"]

    stores = client.get("/api/stores", headers=headers)
    assert stores.status_code == 200
    assert len(stores.json()) == 1
    assert "3245" in stores.json()[0]["address"]


def test_different_address_creates_new_store(client) -> None:
    token = register(client, "stores2@example.com")
    headers = auth_header(token)
    other = ADONIS_OCR.replace("3245 WONDERLAND RD S UNIT A", "100 MAIN ST")

    first = upload_receipt(client, token, ocr_text=ADONIS_OCR)
    second = upload_receipt(client, token, ocr_text=other)
    assert first.json()["store_id"] != second.json()["store_id"]

    stores = client.get("/api/stores", headers=headers)
    assert len(stores.json()) == 2


def test_ocr_address_digit_slip_reuses_store(client) -> None:
    """3045 vs 3245 / postal O-E OCR noise should not create a second Adonis."""
    token = register(client, "ocrslip@example.com")
    headers = auth_header(token)
    slip = ADONIS_OCR.replace("3245 WONDERLAND RD S UNIT A", "3045 WONDERLAND RD S UNIT A").replace(
        "N6L 0E5", "N6L 0E3"
    )
    first = upload_receipt(client, token, ocr_text=ADONIS_OCR)
    second = upload_receipt(client, token, ocr_text=slip)
    assert first.json()["store_id"] == second.json()["store_id"]
    stores = client.get("/api/stores", headers=headers).json()
    assert len(stores) == 1


def test_list_stores_consolidates_legacy_duplicates(client) -> None:
    """Opening /stores merges OCR duplicates already sitting in the DB."""
    token = register(client, "consolidate@example.com")
    headers = auth_header(token)
    created = upload_receipt(client, token, ocr_text=ADONIS_OCR).json()
    assert created["store_id"]
    receipt_id = created["id"]

    engine = client.app.state.test_engine
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == "consolidate@example.com")).first()
        assert user and user.id
        # Older sparse row + richer OCR slip + junk banner leftover.
        sparse = Store(
            user_id=user.id,
            name="ADONIS 101204",
            address="WONDERLAND RD S",
            phone="",
        )
        session.add(sparse)
        session.commit()
        session.refresh(sparse)
        from financial_tracker_api.models import Receipt

        receipt = session.get(Receipt, receipt_id)
        assert receipt is not None
        receipt.store_id = sparse.id
        receipt.store_name = "~~"
        session.add(receipt)
        session.add(
            Store(
                user_id=user.id,
                name="ADONIS 101204",
                address="3045 WONDERLAND RD S UNIT A, LONDON ON N6L 0E3",
                phone="548-488-2782",
            )
        )
        session.add(
            Store(
                user_id=user.id,
                name="Mediterranean market",
                address="3245 WONDERLAND RD S UNIT A, LONDON ON N6L 0E5",
                phone="548-488-2782",
            )
        )
        session.add(
            Store(
                user_id=user.id,
                name="~~",
                address="",
                phone="",
            )
        )
        session.commit()
        before = session.exec(select(Store).where(Store.user_id == user.id)).all()
        assert len(before) >= 4

    stores = client.get("/api/stores", headers=headers)
    assert stores.status_code == 200
    assert len(stores.json()) == 1
    body = stores.json()[0]
    assert "ADONIS" in body["name"].upper()
    assert body["phone"]
    assert "WONDERLAND" in body["address"].upper()

    detail = client.get(f"/api/receipts/{receipt_id}", headers=headers).json()
    assert detail["store_id"] == body["id"]
    assert "ADONIS" in detail["store_name"].upper()


def test_store_helper_edge_cases() -> None:
    from financial_tracker_api.models import Store
    from financial_tracker_api.services.stores import (
        _enrich,
        _name_keys_match,
        _stores_match,
        addresses_compatible,
        is_junk_store_name,
        normalize_phone,
        normalize_store_key,
    )

    assert normalize_phone("(548) 488-2782") == "5484882782"
    assert "o" in normalize_store_key("N6L 0E5", fold_zero=True)
    assert addresses_compatible("", "100 King St") is True
    assert addresses_compatible("100 King St", "100 King St") is True
    assert addresses_compatible("a", "b") is False
    assert is_junk_store_name("Mediterranean market") is True
    assert is_junk_store_name("~~") is True
    assert is_junk_store_name("x") is True
    assert _name_keys_match("", "adonis") is False
    assert _name_keys_match("adonis", "loblaws") is False
    a = Store(id=1, user_id=1, name="ADONIS", address="", phone="111")
    assert _stores_match(a, name_key="loblaws", address="", phone="") is False
    assert _stores_match(a, name_key="adonis", address="", phone="222") is False
    sparse = Store(id=4, user_id=1, name="ADONIS", address="", phone="")
    assert _stores_match(sparse, name_key="adonis", address="", phone="548") is True
    rich = Store(id=2, user_id=1, name="ADONIS 101204", address="Longer addr here", phone="548")
    poor = Store(id=3, user_id=1, name="ADONIS", address="Short", phone="")
    assert _enrich(poor, rich) is True
    assert poor.phone == "548"
    assert "Longer" in poor.address
    assert "101204" in poor.name


def test_consolidate_enriches_keeper_from_duplicate(client) -> None:
    token = register(client, "consolenrich@example.com")
    headers = auth_header(token)
    engine = client.app.state.test_engine
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == "consolenrich@example.com")).first()
        assert user and user.id
        session.add(Store(user_id=user.id, name="ADONIS", address="", phone=""))
        session.add(
            Store(
                user_id=user.id,
                name="ADONIS 101204",
                address="3245 WONDERLAND RD S UNIT A LONDON ON",
                phone="548-488-2782",
            )
        )
        session.commit()

    stores = client.get("/api/stores", headers=headers).json()
    assert len(stores) == 1
    assert stores[0]["phone"] == "548-488-2782"
    assert "3245" in stores[0]["address"]
    assert "101204" in stores[0]["name"]


def test_longer_banner_updates_store_name(client) -> None:
    token = register(client, "longname@example.com")
    short = """\
ADONIS
3245 WONDERLAND RD S UNIT A
LONDON ON N6L 0E5
TEL.: 548-488-2782
Milk 1.00
TOTAL 1.00
"""
    long = short.replace("ADONIS\n", "ADONIS 101204\n")
    first = upload_receipt(client, token, ocr_text=short)
    second = upload_receipt(client, token, ocr_text=long)
    assert first.json()["store_id"] == second.json()["store_id"]
    stores = client.get("/api/stores", headers=auth_header(token)).json()
    assert "101204" in stores[0]["name"]


def test_find_skips_junk_rows_when_matching(client) -> None:
    token = register(client, "skipjunk@example.com")
    headers = auth_header(token)
    engine = client.app.state.test_engine
    with Session(engine) as session:
        user = User(
            email="skipjunk@example.com",
            password_hash="x",
            display_name="x",
        )
        # User already created by register — fetch it.
        session.rollback()
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == "skipjunk@example.com")).first()
        assert user and user.id
        session.add(Store(user_id=user.id, name="~~", address="", phone="548-488-2782"))
        session.commit()

    upload_receipt(client, token, ocr_text=ADONIS_OCR)
    stores = client.get("/api/stores", headers=headers).json()
    assert len(stores) == 1
    assert "ADONIS" in stores[0]["name"].upper()


def test_phone_matches_when_one_address_missing(client) -> None:
    token = register(client, "nophoneaddr@example.com")
    headers = auth_header(token)
    with_phone = """\
ADONIS 101204
TEL.: 548-488-2782
Milk 1.00
TOTAL 1.00
"""
    with_addr = """\
ADONIS 101204
3245 WONDERLAND RD S UNIT A
LONDON ON N6L 0E5
TEL.: 548-488-2782
Bread 2.00
TOTAL 2.00
"""
    first = upload_receipt(client, token, ocr_text=with_phone)
    second = upload_receipt(client, token, ocr_text=with_addr)
    assert first.json()["store_id"] == second.json()["store_id"]
    stores = client.get("/api/stores", headers=headers).json()
    assert len(stores) == 1
    assert "3245" in stores[0]["address"]


def test_junk_store_name_is_not_created(client) -> None:
    token = register(client, "junkname@example.com")
    ocr = """\
~~
Milk 1.00
TOTAL 1.00
"""
    response = upload_receipt(client, token, ocr_text=ocr)
    assert response.status_code == 201
    assert response.json()["store_id"] is None
    stores = client.get("/api/stores", headers=auth_header(token)).json()
    assert stores == []


def test_stores_require_auth(client) -> None:
    assert client.get("/api/stores").status_code == 401


def test_second_upload_enriches_missing_phone(client) -> None:
    token = register(client, "enrich@example.com")
    sparse = """\
ADONIS 101204
3245 WONDERLAND RD S UNIT A
LONDON ON N6L 0E5
Milk 1.00
Total 1.00
"""
    rich = sparse.replace("LONDON ON N6L 0E5", "LONDON ON N6L 0E5\nTEL.: 548-488-2782")
    first = upload_receipt(client, token, ocr_text=sparse)
    second = upload_receipt(client, token, ocr_text=rich)
    assert first.json()["store_id"] == second.json()["store_id"]
    stores = client.get("/api/stores", headers=auth_header(token)).json()
    assert stores[0]["phone"] == "548-488-2782"
