"""Extra API cases that close branch coverage for OCR/parser/auth/stats."""

from pathlib import Path
from unittest.mock import patch

from helpers import SIMPLE_OCR, auth_header, png_bytes, register, upload_receipt
from PIL import Image


def test_update_me_partial_fields(client) -> None:
    token = register(client, "partial@example.com", display_name="Orig")
    headers = auth_header(token)
    only_name = client.patch("/api/auth/me", headers=headers, json={"display_name": "New"})
    assert only_name.json()["display_name"] == "New"
    only_province = client.patch("/api/auth/me", headers=headers, json={"province": "BC"})
    assert only_province.json()["province"] == "BC"


def test_stats_filters_receipts_before_from_date(client) -> None:
    token = register(client, "stats-from@example.com")
    headers = auth_header(token)
    upload_receipt(client, token, ocr_text=SIMPLE_OCR)
    response = client.get(
        "/api/stats/by-category",
        headers=headers,
        params={"from": "2027-01-01"},
    )
    assert response.status_code == 200
    assert response.json()["categories"] == []


def test_ocr_empty_tokens_and_invalid_conf(client, tmp_path: Path) -> None:
    token = register(client, "ocr-edges@example.com")
    image_path = tmp_path / "x.png"
    Image.new("RGB", (32, 32), (255, 255, 255)).save(image_path)

    def _data(*_a, **_k):
        return {"text": ["", "hi", "there"], "conf": ["bad", "-1", "80"]}

    with (
        patch(
            "financial_tracker_api.services.ocr.pytesseract.image_to_data",
            _data,
        ),
        patch(
            "financial_tracker_api.services.ocr.pytesseract.image_to_string",
            return_value="",
        ),
    ):
        response = client.post(
            "/api/receipts/upload",
            headers=auth_header(token),
            files={"file": ("x.png", image_path.read_bytes(), "image/png")},
        )
    assert response.status_code == 201


def test_ocr_no_words_but_plain_text(client) -> None:
    token = register(client, "ocr-plain@example.com")

    def _data(*_a, **_k):
        return {"text": [], "conf": []}

    with (
        patch(
            "financial_tracker_api.services.ocr.pytesseract.image_to_data",
            _data,
        ),
        patch(
            "financial_tracker_api.services.ocr.pytesseract.image_to_string",
            return_value="Solo Store\nItem 1.00\nTOTAL 1.00\n",
        ),
    ):
        response = client.post(
            "/api/receipts/upload",
            headers=auth_header(token),
            files={"file": ("x.png", png_bytes(), "image/png")},
        )
    assert response.status_code == 201
    assert response.json()["store_name"]
    assert response.json()["line_items"]


def test_ocr_completely_empty(client) -> None:
    token = register(client, "ocr-blank@example.com")

    def _data(*_a, **_k):
        return {"text": ["", " "], "conf": ["90", "90"]}

    with (
        patch(
            "financial_tracker_api.services.ocr.pytesseract.image_to_data",
            _data,
        ),
        patch(
            "financial_tracker_api.services.ocr.pytesseract.image_to_string",
            return_value="   ",
        ),
    ):
        response = client.post(
            "/api/receipts/upload",
            headers=auth_header(token),
            files={"file": ("x.png", png_bytes(), "image/png")},
        )
    assert response.status_code == 201
    assert response.json()["line_items"] == []


def test_store_address_enriched_when_longer(client) -> None:
    token = register(client, "addr-enrich@example.com")
    # Same normalized address key; second OCR string is longer after cleanup.
    short = """\
Mart A
100 King St
Item 1.00
TOTAL 1.00
"""
    longer = """\
Mart A
100 King St.
Item 1.00
TOTAL 1.00
"""
    first = upload_receipt(client, token, ocr_text=short)
    second = upload_receipt(client, token, ocr_text=longer)
    assert first.json()["store_id"] == second.json()["store_id"]
    stores = client.get("/api/stores", headers=auth_header(token)).json()
    assert len(stores) == 1
    assert len(stores[0]["address"]) >= len(first.json()["store"]["address"])


def test_credit_total_line_ignored_when_total_present(client) -> None:
    token = register(client, "credit-total@example.com")
    ocr = """\
Shop
Widget 5.00
TOTAL 5.00
CREDIT CR 12.00
"""
    response = upload_receipt(client, token, ocr_text=ocr)
    assert response.json()["total_cents"] == 500


def test_money_fields_are_integer_cents_not_decimals(client) -> None:
    token = register(client, "cents@example.com")
    body = upload_receipt(client, token).json()
    assert isinstance(body["total_cents"], int)
    assert isinstance(body["subtotal_cents"], int)
    assert isinstance(body["tax_total_cents"], int)
    item = body["line_items"][0]
    assert isinstance(item["line_total_cents"], int)
    assert isinstance(item["unit_price_cents"], int)
    assert isinstance(item["tax_amount_cents"], int)
    # $4.99 milk → 499 cents
    milk = next(i for i in body["line_items"] if "milk" in i["name"].lower())
    assert milk["line_total_cents"] == 499


def test_paid_amount_used_when_no_lines(client) -> None:
    token = register(client, "paid-only@example.com")
    ocr = """\
Empty Mart
Account: MASTERCARD CAD$ 12.50
"""
    response = upload_receipt(client, token, ocr_text=ocr)
    assert response.status_code == 201
    assert response.json()["total_cents"] == 1250
    assert response.json()["line_items"] == []


def test_lines_sum_used_when_no_total_or_payment(client) -> None:
    token = register(client, "lines-only@example.com")
    ocr = """\
Mart
Widget 3.25
Gadget 1.75
"""
    response = upload_receipt(client, token, ocr_text=ocr)
    assert response.json()["total_cents"] == 500
    assert response.json()["subtotal_cents"] == 500
