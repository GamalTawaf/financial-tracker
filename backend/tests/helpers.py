"""Shared helpers for API tests (imported by test modules)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from io import BytesIO
from typing import Any
from unittest.mock import patch

from fastapi.testclient import TestClient
from PIL import Image

ADONIS_OCR = """\
ADONIS 101204
3245 WONDERLAND RD S UNIT A
LONDON ON N6L 0E5
TEL.: 548-488-2782
GROCERY
FIVEROSES FLOUR 18.99
MAGIC BAK.POWDER 4.99
P.NUTS&FRUIT
CEDAR FINE COCON 2.99
Saving 1.30
VEGETABLE
JUMBO GRN PEPPER
0.420 kg @ $6.59/kg 2.77
Saving 0.93
TOM.RED CLUSTER
1.505 kg @ $4.39/kg 6.61
Saving 6.63
PEP.GRN LG HOT
0.085 kg @ $11.00/kg 0.93
FRESH BUNCH MINT 0.99
Saving 1.00
SUBTOTAL 33.27
HST 0.00
TOTAL 33.27
CREDIT CR 38.27
Total of your savings 9.86
Account: MASTERCARD CAD$ 38.27
Date/Time: 26/10/24 10:08:06
"""

SIMPLE_OCR = """\
Loblaws
123 Main St
Toronto ON M5V 1A1
TEL.: 416-555-0100
2026-10-15
Milk 2% 4.99
Potato Chips 3.49
Whole Wheat Bread 2.99
Subtotal 11.47
HST 0.45
Total 11.92
"""


def png_bytes(
    size: tuple[int, int] = (64, 64), color: tuple[int, int, int] = (255, 255, 255)
) -> bytes:
    image = Image.new("RGB", size, color=color)
    buf = BytesIO()
    image.save(buf, format="PNG")
    return buf.getvalue()


def register(client: TestClient, email: str, password: str = "Password123!ab", **extra: Any) -> str:
    body = {"email": email, "password": password, "display_name": extra.get("display_name", email)}
    response = client.post("/api/auth/register", json=body)
    assert response.status_code == 201, response.text
    return response.json()["access_token"]


def auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@contextmanager
def mock_ocr(text: str = SIMPLE_OCR) -> Iterator[None]:
    """Stub Tesseract only — upload still writes the file and runs the parser."""

    def _image_to_string(*_args: Any, **_kwargs: Any) -> str:
        return text

    def _image_to_data(*_args: Any, **_kwargs: Any) -> dict[str, list]:
        words = [w for w in text.replace("\n", " ").split(" ") if w]
        return {
            "text": words,
            "conf": ["90"] * len(words),
        }

    with (
        patch("financial_tracker_api.services.ocr.pytesseract.image_to_string", _image_to_string),
        patch("financial_tracker_api.services.ocr.pytesseract.image_to_data", _image_to_data),
    ):
        yield


@contextmanager
def mock_ocr_result(text: str, confidence: float) -> Iterator[None]:
    """Mock OCR service return when confidence must be controlled precisely."""
    with patch(
        "financial_tracker_api.routers.receipts.run_ocr",
        return_value=(text, confidence),
    ):
        yield


def upload_receipt(
    client: TestClient,
    token: str,
    *,
    ocr_text: str = SIMPLE_OCR,
    confidence: float | None = None,
    filename: str = "receipt.png",
    content_type: str = "image/png",
    content: bytes | None = None,
):
    data = content if content is not None else png_bytes()
    headers = auth_header(token)
    if confidence is None:
        with mock_ocr(ocr_text):
            return client.post(
                "/api/receipts/upload",
                headers=headers,
                files={"file": (filename, data, content_type)},
            )
    with mock_ocr_result(ocr_text, confidence):
        return client.post(
            "/api/receipts/upload",
            headers=headers,
            files={"file": (filename, data, content_type)},
        )
