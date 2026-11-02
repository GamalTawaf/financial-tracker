"""Parser edge cases exercised only through /api/receipts/upload."""

from helpers import register, upload_receipt


def test_invalid_date_token_ignored(client) -> None:
    token = register(client, "baddate@example.com")
    ocr = """\
Date Shop
99/99/99
Milk 1.00
TOTAL 1.00
"""
    response = upload_receipt(client, token, ocr_text=ocr)
    assert response.status_code == 201
    assert response.json()["purchased_at"] is None


def test_header_breaks_on_grocery_section(client) -> None:
    token = register(client, "section@example.com")
    ocr = """\
ADONIS
GROCERY
Flour 2.00
TOTAL 2.00
"""
    response = upload_receipt(client, token, ocr_text=ocr)
    assert response.status_code == 201
    assert (
        response.json()["store"]["address"] in ("", None)
        or response.json()["store"]["address"] == ""
    )


def test_priced_skip_name_and_short_name(client) -> None:
    token = register(client, "skipprice@example.com")
    ocr = """\
Shop
X 1.00
Total 9.99
Milk 3.00
TOTAL 3.00
"""
    response = upload_receipt(client, token, ocr_text=ocr)
    assert response.status_code == 201
    names = [i["name"].lower() for i in response.json()["line_items"]]
    assert any("milk" in n for n in names)
    assert not any(n == "x" for n in names)


def test_amount_on_account_line_does_not_override_total(client) -> None:
    token = register(client, "account-total@example.com")
    ocr = """\
Shop
Milk 5.00
TOTAL 5.00
Account: MASTERCARD CAD$ 99.00
"""
    response = upload_receipt(client, token, ocr_text=ocr)
    assert response.json()["total_cents"] == 500


def test_noisy_address_punctuation_tokens(client) -> None:
    token = register(client, "punct@example.com")
    ocr = """\
Mart
---
100 King Rd Unit A
Toronto ON M5H 1A1 junk extra
TEL.: 416-555-9999
Milk 1.00
TOTAL 1.00
"""
    response = upload_receipt(client, token, ocr_text=ocr)
    assert response.status_code == 201
    address = response.json()["store"]["address"].upper()
    assert "KING" in address
    assert "JUNK" not in address


def test_alternate_date_formats(client) -> None:
    token = register(client, "dates@example.com")
    ocr = """\
Shop
15-10-2026
Milk 1.00
TOTAL 1.00
"""
    response = upload_receipt(client, token, ocr_text=ocr)
    assert response.json()["purchased_at"] == "2026-10-15"


def test_phone_line_between_address_parts(client) -> None:
    token = register(client, "phoneaddr@example.com")
    ocr = """\
Mart
100 King Rd
TEL.: 416-555-1212
Toronto ON M5H 1A1
Milk 1.00
TOTAL 1.00
"""
    response = upload_receipt(client, token, ocr_text=ocr)
    assert response.json()["store"]["phone"] == "416-555-1212"


def test_grand_total_label_sets_total(client) -> None:
    token = register(client, "grand@example.com")
    ocr = """\
Shop
Milk 2.00
Amount Total 2.00
"""
    response = upload_receipt(client, token, ocr_text=ocr)
    assert response.json()["total_cents"] == 200


def test_address_line_that_cleans_to_empty_skipped(client) -> None:
    token = register(client, "emptyaddr@example.com")
    ocr = """\
ShopX
*** ###
Milk 1.00
TOTAL 1.00
"""
    response = upload_receipt(client, token, ocr_text=ocr)
    assert response.status_code == 201


def test_address_strips_punct_and_short_noise_tokens(client) -> None:
    token = register(client, "noise@example.com")
    ocr = """\
MartX
100 *** by King Rd Unit A
Toronto ON M5H 1A1
Milk 1.00
TOTAL 1.00
"""
    response = upload_receipt(client, token, ocr_text=ocr)
    assert response.status_code == 201
    address = response.json()["store"]["address"].upper()
    assert "KING" in address
    assert "***" not in address
    assert " BY " not in f" {address} "
