"""Local Tesseract OCR wrapper."""

from __future__ import annotations

from pathlib import Path

import pytesseract
from PIL import Image, ImageOps

# Single uniform block of text — best for tall thermal receipts.
_OCR_CONFIG = "--oem 3 --psm 6"


def _load_for_ocr(image_path: Path) -> Image.Image:
    """Open and normalize an image so pytesseract accepts it.

    iPhone photos often open as MPO (``MpoImageFile``), which pytesseract
    rejects with ``Unsupported image format/type``. EXIF-transpose + RGB
    yields a plain ``PIL.Image.Image``.
    """
    with Image.open(image_path) as raw:
        image = ImageOps.exif_transpose(raw)
        return image.convert("RGB")


def run_ocr(image_path: Path) -> tuple[str, float]:
    """Return (text, mean_confidence 0-1) for an image path."""
    image = _load_for_ocr(image_path)
    data = pytesseract.image_to_data(
        image, config=_OCR_CONFIG, output_type=pytesseract.Output.DICT
    )
    texts: list[str] = []
    confidences: list[float] = []
    for text, conf in zip(data.get("text", []), data.get("conf", []), strict=False):
        token = (text or "").strip()
        try:
            conf_val = float(conf)
        except (TypeError, ValueError):
            conf_val = -1
        if not token or conf_val < 0:
            continue
        texts.append(token)
        confidences.append(conf_val / 100.0)

    plain = pytesseract.image_to_string(image, config=_OCR_CONFIG).strip()
    if not plain and texts:
        plain = " ".join(texts)

    if not texts:
        return plain, 0.4 if plain else 0.0

    mean_conf = sum(confidences) / len(confidences)
    return plain, mean_conf
