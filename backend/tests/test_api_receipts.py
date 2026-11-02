"""Receipt upload/list/get/patch endpoints as a client would call them."""

from unittest.mock import patch

from helpers import (
    ADONIS_OCR,
    SIMPLE_OCR,
    auth_header,
    png_bytes,
    register,
    upload_receipt,
)
from PIL import Image


def test_upload_parses_line_items_and_totals(client) -> None:
    token = register(client, "receipts@example.com")
    response = upload_receipt(client, token, ocr_text=SIMPLE_OCR)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["store_name"].startswith("Loblaws")
    assert body["store_id"] is not None
    assert body["store"]["address"]
    assert body["purchased_at"] == "2026-10-15"
    assert body["subtotal_cents"] == 1147
    assert body["tax_total_cents"] == 45
    assert body["total_cents"] == 1192
    names = {item["name"].lower() for item in body["line_items"]}
    assert any("milk" in name for name in names)
    assert any("chips" in name for name in names)
    assert any("bread" in name for name in names)


def test_upload_adonis_style_and_skips_savings(client) -> None:
    token = register(client, "adonis@example.com")
    response = upload_receipt(client, token, ocr_text=ADONIS_OCR)
    assert response.status_code == 201, response.text
    body = response.json()
    assert "ADONIS" in body["store_name"].upper()
    assert "3245" in body["store"]["address"]
    assert body["store"]["phone"]
    assert body["purchased_at"] == "2026-10-24"
    # Lines + Mastercard are $38.27; OCR often misreads TOTAL as $33.27.
    assert body["total_cents"] == 3827
    assert body["subtotal_cents"] == 3827
    names = [item["name"].upper() for item in body["line_items"]]
    assert any("FLOUR" in name for name in names)
    assert any("PEPPER" in name for name in names)
    assert all("SAVING" not in name for name in names)
    pepper = next(item for item in body["line_items"] if "PEPPER" in item["name"].upper())
    assert pepper["line_total_cents"] == 277
    assert abs(pepper["quantity"] - 0.42) < 0.001
    assert pepper["quantity_unit"] == "kg"
    lines_sum = sum(item["line_total_cents"] for item in body["line_items"])
    assert lines_sum == body["total_cents"]
    # Adonis prints section headers above items (GROCERY / VEGETABLE).
    flour = next(item for item in body["line_items"] if "FLOUR" in item["name"].upper())
    mint = next(item for item in body["line_items"] if "MINT" in item["name"].upper())
    assert flour["category"] == "grocery"
    assert flour["quantity_unit"] == "ea"
    assert pepper["category"] == "vegetable"
    assert mint["category"] == "vegetable"
    assert mint["quantity_unit"] == "ea"


def test_upload_parses_lb_weight_unit(client) -> None:
    token = register(client, "lb@example.com")
    ocr = """\
Butcher
Ground Beef
1.250 lb @ $6.99/lb 8.74
TOTAL 8.74
"""
    response = upload_receipt(client, token, ocr_text=ocr)
    assert response.status_code == 201
    beef = next(i for i in response.json()["line_items"] if "BEEF" in i["name"].upper())
    assert abs(beef["quantity"] - 1.25) < 0.001
    assert beef["quantity_unit"] == "lb"


def test_weight_line_prefers_qty_times_rate_over_ocr_extension(client) -> None:
    """OCR often reads 2.77 as 2.71; trust 0.420 kg × $6.59."""
    token = register(client, "weighmath@example.com")
    ocr = """\
Produce
JUMBO GRN PEPPER
0.420 kg @ $6.59/kg 2.71
TOTAL 2.77
Account: MASTERCARD CAD$ 2.77
"""
    response = upload_receipt(client, token, ocr_text=ocr)
    assert response.status_code == 201
    pepper = response.json()["line_items"][0]
    assert pepper["line_total_cents"] == 277
    assert response.json()["total_cents"] == 277


def test_weight_line_keeps_printed_when_far_from_qty_rate(client) -> None:
    token = register(client, "manualprice@example.com")
    ocr = """\
Produce
Special Melon
1.000 kg @ $4.00/kg 1.50
TOTAL 1.50
"""
    response = upload_receipt(client, token, ocr_text=ocr)
    melon = response.json()["line_items"][0]
    assert melon["line_total_cents"] == 150


def test_list_get_patch_receipt_and_line_item(client) -> None:
    token = register(client, "flow@example.com")
    headers = auth_header(token)
    created = upload_receipt(client, token, ocr_text=SIMPLE_OCR).json()
    receipt_id = created["id"]
    item_id = created["line_items"][0]["id"]

    listed = client.get("/api/receipts", headers=headers)
    assert listed.status_code == 200
    assert any(row["id"] == receipt_id for row in listed.json())

    got = client.get(f"/api/receipts/{receipt_id}", headers=headers)
    assert got.status_code == 200
    assert got.json()["id"] == receipt_id

    patched = client.patch(
        f"/api/receipts/{receipt_id}",
        headers=headers,
        json={
            "store_name": "Loblaws Queen",
            "needs_review": False,
            "review_reasons": [],
            "purchased_at": "2026-10-16",
        },
    )
    assert patched.status_code == 200
    assert patched.json()["store_name"] == "Loblaws Queen"
    assert patched.json()["purchased_at"] == "2026-10-16"
    assert patched.json()["needs_review"] is False

    item = client.patch(
        f"/api/receipts/line-items/{item_id}",
        headers=headers,
        json={"name": "Milk 2% Organic", "category": "dairy", "tax_status": "zero_rated"},
    )
    assert item.status_code == 200
    assert item.json()["name"] == "Milk 2% Organic"
    assert item.json()["category"] == "dairy"


def test_delete_receipt_removes_it_and_line_items(client) -> None:
    token = register(client, "delete@example.com")
    headers = auth_header(token)
    created = upload_receipt(client, token, ocr_text=SIMPLE_OCR).json()
    receipt_id = created["id"]
    item_id = created["line_items"][0]["id"]

    deleted = client.delete(f"/api/receipts/{receipt_id}", headers=headers)
    assert deleted.status_code == 204

    assert client.get(f"/api/receipts/{receipt_id}", headers=headers).status_code == 404
    assert (
        client.patch(
            f"/api/receipts/line-items/{item_id}",
            headers=headers,
            json={"name": "gone"},
        ).status_code
        == 404
    )
    listed = client.get("/api/receipts", headers=headers)
    assert all(row["id"] != receipt_id for row in listed.json())


def test_cannot_delete_another_users_receipt(client) -> None:
    token_a = register(client, "del-owner@example.com")
    token_b = register(client, "del-other@example.com")
    receipt_id = upload_receipt(client, token_a, ocr_text=SIMPLE_OCR).json()["id"]

    forbidden = client.delete(f"/api/receipts/{receipt_id}", headers=auth_header(token_b))
    assert forbidden.status_code == 404
    assert (
        client.get(f"/api/receipts/{receipt_id}", headers=auth_header(token_a)).status_code == 200
    )


def test_delete_missing_receipt_returns_404(client) -> None:
    token = register(client, "del-missing@example.com")
    assert client.delete("/api/receipts/9999", headers=auth_header(token)).status_code == 404


def test_user_cannot_read_or_patch_other_users_receipt(client) -> None:
    token_a = register(client, "owner@example.com")
    token_b = register(client, "other@example.com")
    receipt = upload_receipt(client, token_a, ocr_text=SIMPLE_OCR).json()
    receipt_id = receipt["id"]
    item_id = receipt["line_items"][0]["id"]

    assert (
        client.get(f"/api/receipts/{receipt_id}", headers=auth_header(token_b)).status_code == 404
    )
    assert (
        client.patch(
            f"/api/receipts/{receipt_id}",
            headers=auth_header(token_b),
            json={"store_name": "Nope"},
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/receipts/line-items/{item_id}",
            headers=auth_header(token_b),
            json={"name": "Stolen"},
        ).status_code
        == 404
    )


def test_upload_rejects_unsupported_type_and_oversized(client) -> None:
    token = register(client, "badfile@example.com")
    headers = auth_header(token)
    bad_type = client.post(
        "/api/receipts/upload",
        headers=headers,
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert bad_type.status_code == 400

    with patch("financial_tracker_api.routers.receipts.run_ocr", return_value=("X", 0.9)):
        huge = client.post(
            "/api/receipts/upload",
            headers=headers,
            files={"file": ("big.png", b"x" * (12 * 1024 * 1024 + 1), "image/png")},
        )
    assert huge.status_code == 400
    assert "large" in huge.json()["detail"].lower()


def test_upload_ocr_failure_returns_422(client) -> None:
    token = register(client, "ocrfail@example.com")
    with patch(
        "financial_tracker_api.routers.receipts.run_ocr",
        side_effect=TypeError("Unsupported image format/type"),
    ):
        response = client.post(
            "/api/receipts/upload",
            headers=auth_header(token),
            files={"file": ("receipt.png", png_bytes(), "image/png")},
        )
    assert response.status_code == 422
    assert "Could not read" in response.json()["detail"]


def test_get_missing_receipt_and_line_item(client) -> None:
    token = register(client, "missing@example.com")
    headers = auth_header(token)
    assert client.get("/api/receipts/9999", headers=headers).status_code == 404
    assert (
        client.patch(
            "/api/receipts/line-items/9999",
            headers=headers,
            json={"name": "x"},
        ).status_code
        == 404
    )


def test_low_ocr_confidence_flags_receipt(client) -> None:
    token = register(client, "lowconf@example.com")
    response = upload_receipt(
        client,
        token,
        ocr_text="Mystery Mart\nUnknown Snack 1.00\nTotal 1.00\n",
        confidence=0.2,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["needs_review"] is True
    assert "low_ocr_confidence" in body["review_reasons"]


def test_empty_ocr_flags_no_line_items(client) -> None:
    token = register(client, "empty@example.com")
    response = upload_receipt(client, token, ocr_text="\n\n", confidence=0.9)
    assert response.status_code == 201
    body = response.json()
    assert body["needs_review"] is True
    assert "no_line_items" in body["review_reasons"]
    assert "missing_store" in body["review_reasons"]


def test_upload_mpo_phone_photo_normalizes_for_ocr(client, tmp_path) -> None:
    """iPhone MPO images must load; Tesseract itself stays mocked."""
    token = register(client, "iphone@example.com")
    path = tmp_path / "IMG_phone.mpo"
    frame = Image.new("RGB", (64, 48), (240, 240, 240))
    frame.save(path, format="MPO", save_all=True, append_images=[frame.copy()])
    content = path.read_bytes()

    response = upload_receipt(
        client,
        token,
        ocr_text=SIMPLE_OCR,
        filename="IMG_1732.JPG",
        content_type="image/jpeg",
        content=content,
    )
    assert response.status_code == 201, response.text
    assert response.json()["line_items"]


def test_tax_and_subtotal_mismatch_flags(client) -> None:
    token = register(client, "mismatch@example.com")
    ocr = """\
Corner Store
2026-01-01
Candy Bar 10.00
Subtotal 50.00
HST 9.00
Total 59.00
"""
    response = upload_receipt(client, token, ocr_text=ocr, confidence=0.95)
    assert response.status_code == 201
    reasons = response.json()["review_reasons"]
    assert "subtotal_mismatch" in reasons
    assert "tax_total_mismatch" in reasons


def test_weight_line_without_inline_total(client) -> None:
    token = register(client, "weight@example.com")
    ocr = """\
Produce Mart
100 King St W
Toronto ON M5H 1A1
APPLES FUJI
0.500 kg @ $4.00/kg
Subtotal 2.00
TOTAL 2.00
"""
    response = upload_receipt(client, token, ocr_text=ocr)
    assert response.status_code == 201
    apples = next(i for i in response.json()["line_items"] if "APPLE" in i["name"].upper())
    assert apples["line_total_cents"] == 200
    assert abs(apples["quantity"] - 0.5) < 0.001
    assert apples["quantity_unit"] == "kg"


def test_total_falls_back_to_subtotal(client) -> None:
    token = register(client, "fallback@example.com")
    ocr = """\
Mini Mart
Milk 2.00
Subtotal 2.00
"""
    response = upload_receipt(client, token, ocr_text=ocr)
    assert response.status_code == 201
    assert response.json()["total_cents"] == 200


def test_adonts_ocr_typo_normalized_in_store(client) -> None:
    token = register(client, "adonts@example.com")
    ocr = """\
ADONTS 101204
3245 WONDERLAND RD S UNIT A
LONDON ON N6L OES
TEL.: 548-488-2782
Flour 1.00
TOTAL 1.00
"""
    response = upload_receipt(client, token, ocr_text=ocr)
    assert response.status_code == 201
    assert response.json()["store"]["name"].upper().startswith("ADONIS")
    assert "0E5" in response.json()["store"]["address"].upper().replace(" ", "")


def test_adonis_bakery_count_at_price_and_garbled_totals(client) -> None:
    """Real bakery slip: OCR turns $8.37 into 38.37/3.37; trust lines + card."""
    token = register(client, "bakery@example.com")
    ocr = """\
- ~~
Mediterranean market
ADONIS 101204
3245 WONDERLAND RD S UNIT A
LONDON ON N6L 0E3
TEL. : 548-488-2782 |
BAKERY
(2)ADONIS WH.BRAN P
2 @ $1.89 3.78
RFS PR.MEALS
ADONIS GARLIC SC 4.59
SUBTOT AL. 38.37
TOT AL 3.37
CREDIT CR 8.37
Total number of items sold = 3
Account: MASTERCARD CAD$ 8.37
DateTime: 26/10/29 14:49:25
10/29/2026 101204
"""
    response = upload_receipt(client, token, ocr_text=ocr)
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["store_name"].upper().startswith("ADONIS")
    assert "3245" in (body["store"]["address"] or "")
    assert body["purchased_at"] == "2026-10-29"
    assert body["total_cents"] == 837
    assert body["subtotal_cents"] == 837
    names = {item["name"].upper() for item in body["line_items"]}
    assert any("BRAN" in n for n in names)
    assert any("GARLIC" in n for n in names)
    assert not any("TOT" == n or n.startswith("TOT ") for n in names)
    bran = next(i for i in body["line_items"] if "BRAN" in i["name"].upper())
    assert bran["quantity"] == 2
    assert bran["quantity_unit"] == "ea"
    assert bran["line_total_cents"] == 378
    assert bran["category"] == "bakery"
    garlic = next(i for i in body["line_items"] if "GARLIC" in i["name"].upper())
    assert garlic["line_total_cents"] == 459
    assert garlic["category"] == "prepared"
    assert sum(i["line_total_cents"] for i in body["line_items"]) == 837


def test_count_at_price_without_extension_and_far_mismatch(client) -> None:
    token = register(client, "countat@example.com")
    ocr = """\
Corner Bakery
Dinner Rolls
3 @ $2.00
Croissant
2 @ $1.50 9.99
Baguette
2 @ $1.89 3.71
TOTAL 15.99
"""
    response = upload_receipt(client, token, ocr_text=ocr)
    assert response.status_code == 201
    rolls = next(i for i in response.json()["line_items"] if "ROLL" in i["name"].upper())
    assert rolls["quantity"] == 3
    assert rolls["line_total_cents"] == 600
    croissant = next(i for i in response.json()["line_items"] if "CROISSANT" in i["name"].upper())
    # Printed 9.99 is far from 2×1.50=3.00 → keep printed.
    assert croissant["line_total_cents"] == 999
    baguette = next(i for i in response.json()["line_items"] if "BAGUETTE" in i["name"].upper())
    # 3.71 vs 3.78 → OCR slip, prefer qty×rate.
    assert baguette["line_total_cents"] == 378


def test_store_name_falls_back_when_banner_is_junk(client) -> None:
    token = register(client, "junkstore@example.com")
    ocr = """\
~~
100 King St
TEL.: 416-555-0100
GROCERY
Milk 1.00
TOTAL 1.00
"""
    response = upload_receipt(client, token, ocr_text=ocr)
    assert response.status_code == 201
    assert response.json()["line_items"]


def test_patch_receipt_individual_fields(client) -> None:
    token = register(client, "patchbits@example.com")
    headers = auth_header(token)
    receipt_id = upload_receipt(client, token).json()["id"]
    assert (
        client.patch(
            f"/api/receipts/{receipt_id}",
            headers=headers,
            json={"store_name": "Only Name"},
        ).status_code
        == 200
    )
    assert (
        client.patch(
            f"/api/receipts/{receipt_id}",
            headers=headers,
            json={"purchased_at": "2026-02-02"},
        ).json()["purchased_at"]
        == "2026-02-02"
    )
    assert (
        client.patch(
            f"/api/receipts/{receipt_id}",
            headers=headers,
            json={"needs_review": True},
        ).json()["needs_review"]
        is True
    )
    assert client.patch(
        f"/api/receipts/{receipt_id}",
        headers=headers,
        json={"review_reasons": ["manual"]},
    ).json()["review_reasons"] == ["manual"]
