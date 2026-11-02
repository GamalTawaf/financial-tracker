"""Safe receipt image upload helpers."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, UnidentifiedImageError

# Maps detected format → canonical extension.
_FORMAT_EXTENSIONS = {
    "JPEG": ".jpg",
    "MPO": ".jpg",  # iPhone multi-picture → treat as JPEG
    "PNG": ".png",
    "WEBP": ".webp",
    "GIF": ".gif",
}
ALLOWED_EXTENSIONS = frozenset(_FORMAT_EXTENSIONS.values())


def sniff_image_extension(content: bytes) -> str:
    """Return a safe image extension after verifying the payload is a real image.

    Raises ValueError when the bytes are not an allowed image.
    """
    if not content:
        raise ValueError("Empty file")
    try:
        from io import BytesIO

        with Image.open(BytesIO(content)) as image:
            image.verify()
        with Image.open(BytesIO(content)) as image:
            fmt = (image.format or "").upper()
    except (UnidentifiedImageError, OSError) as exc:
        raise ValueError("File is not a valid image") from exc
    extension = _FORMAT_EXTENSIONS.get(fmt)
    if extension is None:
        raise ValueError(f"Unsupported image format: {fmt or 'unknown'}")
    return extension


def resolve_receipt_path(data_dir: Path, relative_image_path: str) -> Path:
    """Resolve a stored relative image path under data_dir (no path escape)."""
    relative = Path(relative_image_path)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Invalid image path")
    full = (data_dir / relative).resolve()
    data_root = data_dir.resolve()
    if not str(full).startswith(str(data_root)):
        raise ValueError("Invalid image path")
    return full


def delete_receipt_image(data_dir: Path, relative_image_path: str) -> None:
    """Best-effort delete of a receipt image file."""
    try:
        path = resolve_receipt_path(data_dir, relative_image_path)
    except ValueError:
        return
    if path.is_file():
        path.unlink(missing_ok=True)
