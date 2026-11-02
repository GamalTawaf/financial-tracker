"""Store list + find-or-create via receipt uploads."""

from helpers import ADONIS_OCR, auth_header, register, upload_receipt


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
