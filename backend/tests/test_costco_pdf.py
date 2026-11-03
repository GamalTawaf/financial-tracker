"""Costco Orders & Purchases PDF upload + parse."""

from __future__ import annotations

from helpers import auth_header, register

from financial_tracker_api.services.parser import parse_receipt_text
from financial_tracker_api.services.uploads import sniff_image_extension

COSTCO_ORDERS_TEXT = """\
11/2/26, 3:15 PM
Orders & Purchases | Costco
N LONDON #530
693 WONDERLAND RD N
LONDON, ON N6H 4L1
22053001102962610311601
Member
111940332102
57554 BLUEBERRIES 12.99 N
332918 KEFIR 2L 6.99 N
2115339 ROCCO ROMA 5.99 N
BAKER POTATO 12.99 N
881393 LIMES 3 LB. 7.99 N
427367 SOFT CR CHSE 13.49 N
1350409 GARLIC CHEES 9.99 N
30669 BANANAS 1.69 N
3460840 2% LIBERTE 13.99 N
313740 **KS FACIAL* 22.99 Y
HOMO MILK 7.09 N
1968094 CILANTRO 4.99 N
1610610 AA SPAGHETTI 12.99 N
25771 MINI CUKES 4.99 N
1706959 KS FR EGGS 8.99 N
SUBTOTAL
165.63
TAX
2.99
TOTAL
168.62
XXXXXXXXXXXXX3236
APPROVED -PURCHASE
AMOUNT: $168.62
10/31/2026 16:01 530 11 296 73
MASTER CARD
"""


def _raw_text_pdf(text: str) -> bytes:
    """Hand-rolled one-page PDF with extractable Latin-1 text."""
    content_ops = ["BT /F1 10 Tf"]
    for i, line in enumerate(text.splitlines()[:80]):
        safe = (
            line.encode("latin-1", errors="replace")
            .decode("latin-1")
            .replace("\\", "\\\\")
            .replace("(", "\\(")
            .replace(")", "\\)")
        )
        if i == 0:
            content_ops.append(f"50 750 Td ({safe}) Tj")
        else:
            content_ops.append(f"0 -12 Td ({safe}) Tj")
    content_ops.append("ET")
    stream = "\n".join(content_ops).encode("latin-1")
    objects: list[bytes] = []

    def obj(n: int, body: bytes) -> None:
        objects.append(f"{n} 0 obj\n".encode() + body + b"\nendobj\n")

    obj(1, b"<< /Type /Catalog /Pages 2 0 R >>")
    obj(2, b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    obj(
        3,
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    )
    obj(4, f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream")
    obj(5, b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for chunk in objects:
        offsets.append(len(out))
        out.extend(chunk)
    xref_pos = len(out)
    out.extend(f"xref\n0 {len(offsets)}\n".encode())
    out.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        out.extend(f"{off:010d} 00000 n \n".encode())
    out.extend(
        f"trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_pos}\n%%EOF\n".encode()
    )
    return bytes(out)


def test_sniff_accepts_pdf() -> None:
    pdf = _raw_text_pdf("hello")
    assert sniff_image_extension(pdf) == ".pdf"


def test_empty_pdf_text_raises(tmp_path) -> None:
    from financial_tracker_api.services.ocr import extract_receipt_text

    blank = tmp_path / "blank.pdf"
    blank.write_bytes(_raw_text_pdf(""))
    try:
        extract_receipt_text(blank)
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "extractable" in str(exc).lower()


def test_costco_tax_status_helper() -> None:
    from financial_tracker_api.services.parser import _costco_tax_status

    assert _costco_tax_status(None) is None
    assert _costco_tax_status("") is None
    assert _costco_tax_status("n") == "zero_rated"
    assert _costco_tax_status("Y") == "taxable"


def test_costco_without_warehouse_code() -> None:
    parsed = parse_receipt_text(
        "Orders & Purchases | Costco\nMember\n111\nAPPLES 1.00 N\nSUBTOTAL\n1.00\nTOTAL\n1.00\n"
    )
    assert parsed.store_name == "COSTCO"


def test_costco_price_on_following_line() -> None:
    parsed = parse_receipt_text(
        "Orders & Purchases | Costco\nLONDON #530\n100 MAIN ST\n"
        "BANANAS\n1.69 N\nSUBTOTAL\n1.69\nTAX\n0.00\nTOTAL\n1.69\n"
    )
    assert any(
        line.name.upper() == "BANANAS" and line.line_total_cents == 169 for line in parsed.lines
    )


def test_costco_item_stops_address_scan() -> None:
    parsed = parse_receipt_text(
        "Orders & Purchases | Costco\nLONDON #999\n"
        "57554 BLUEBERRIES 12.99 N\nSUBTOTAL\n12.99\nTOTAL\n12.99\n"
    )
    assert "COSTCO" in parsed.store_name.upper()
    assert any("BLUEBERRIES" in line.name.upper() for line in parsed.lines)


def test_parse_costco_orders_and_purchases_text() -> None:
    parsed = parse_receipt_text(COSTCO_ORDERS_TEXT)
    assert "COSTCO" in parsed.store_name.upper()
    assert "530" in parsed.store_name or "530" in (parsed.store_address or "")
    assert "WONDERLAND" in (parsed.store_address or "").upper()
    assert parsed.purchased_at is not None
    assert parsed.purchased_at.isoformat() == "2026-10-31"
    assert parsed.subtotal_cents == 16563
    assert parsed.tax_total_cents == 299
    assert parsed.total_cents == 16862
    names = " ".join(line.name.upper() for line in parsed.lines)
    assert "BLUEBERRIES" in names
    assert "KEFIR" in names
    assert "FACIAL" in names
    assert len(parsed.lines) >= 14
    assert not any(line.name.upper().startswith("AMOUNT") for line in parsed.lines)
    by_name = {line.name.upper(): line for line in parsed.lines}
    assert by_name["BLUEBERRIES"].tax_status == "zero_rated"
    facial = next(line for line in parsed.lines if "FACIAL" in line.name.upper())
    assert facial.tax_status == "taxable"


def test_upload_costco_applies_ny_tax_flags(client) -> None:
    token = register(client, "costcotax@example.com")
    pdf = _raw_text_pdf(COSTCO_ORDERS_TEXT)
    response = client.post(
        "/api/receipts/upload",
        headers=auth_header(token),
        files={"file": ("costco.pdf", pdf, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    items = {item["name"].upper(): item for item in response.json()["line_items"]}
    assert items["BLUEBERRIES"]["tax_status"] == "zero_rated"
    assert items["BLUEBERRIES"]["tax_amount_cents"] == 0
    facial = next(
        item for item in response.json()["line_items"] if "FACIAL" in item["name"].upper()
    )
    assert facial["tax_status"] == "taxable"
    assert facial["tax_amount_cents"] == 299  # 13% of 2299
    assert response.json()["tax_total_cents"] == 299


def test_upload_costco_pdf_extracts_text(client) -> None:
    token = register(client, "costcopdf@example.com")
    pdf = _raw_text_pdf(COSTCO_ORDERS_TEXT)
    response = client.post(
        "/api/receipts/upload",
        headers=auth_header(token),
        files={"file": ("Orders & Purchases _ Costco.pdf", pdf, "application/pdf")},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["total_cents"] == 16862
    assert body["subtotal_cents"] == 16563
    assert body["tax_total_cents"] == 299
    assert any("BLUEBERRIES" in item["name"].upper() for item in body["line_items"])
    assert body["has_image"] is True

    image = client.get(f"/api/receipts/{body['id']}/image", headers=auth_header(token))
    assert image.status_code == 200
    assert "pdf" in image.headers["content-type"]
