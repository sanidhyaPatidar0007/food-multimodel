"""Upload validation by size and *content* (magic bytes), never trusting the filename alone."""
from __future__ import annotations

import io

from PIL import Image, ImageOps, UnidentifiedImageError

from .errors import MediaError, PayloadTooLarge, UnsupportedMediaType

IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
VIDEO_TYPES = {"video/mp4", "video/webm", "video/quicktime", "video/x-msvideo"}
MAX_PIXELS = 40_000_000
Image.MAX_IMAGE_PIXELS = MAX_PIXELS


def sniff_image(data: bytes) -> str | None:
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def sniff_video(data: bytes) -> str | None:
    if data[4:8] == b"ftyp":
        return "video/quicktime" if data[8:12] == b"qt  " else "video/mp4"
    if data[:4] == b"\x1a\x45\xdf\xa3":
        return "video/webm"
    if data[:4] == b"RIFF" and data[8:12] == b"AVI ":
        return "video/x-msvideo"
    return None


def validate_image_bytes(data: bytes, max_bytes: int) -> Image.Image:
    """Return a decoded RGB PIL image or raise a MediaError subclass."""
    if not data:
        raise MediaError("The uploaded file is empty.")
    if len(data) > max_bytes:
        raise PayloadTooLarge(f"Image is larger than the {max_bytes // (1024 * 1024)} MB limit.")
    if sniff_image(data) is None:
        raise UnsupportedMediaType("Unsupported image type. Upload a JPEG, PNG or WebP file.")
    try:
        img = Image.open(io.BytesIO(data))
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise MediaError("The image could not be decoded; it may be corrupted.") from exc
    img = ImageOps.exif_transpose(img)
    if img.width < 32 or img.height < 32:
        raise MediaError("Image is too small to analyse (minimum 32x32 pixels).")
    return img.convert("RGB")


def validate_video_bytes(data: bytes, max_bytes: int) -> str:
    """Validate container type and size. Returns the sniffed MIME type."""
    if not data:
        raise MediaError("The uploaded file is empty.")
    if len(data) > max_bytes:
        raise PayloadTooLarge(f"Video is larger than the {max_bytes // (1024 * 1024)} MB limit.")
    kind = sniff_video(data)
    if kind is None:
        raise UnsupportedMediaType("Unsupported video type. Upload MP4, WebM, MOV or AVI.")
    return kind
