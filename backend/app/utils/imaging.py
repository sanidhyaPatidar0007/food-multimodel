"""Image preprocessing and quality checks (Pillow + OpenCV + NumPy)."""
from __future__ import annotations

import base64
import io

import cv2
import numpy as np
from PIL import Image

IMAGENET_MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
IMAGENET_STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)

BLUR_THRESHOLD = 60.0       # variance of Laplacian below this => too blurry
DARK_THRESHOLD = 40.0       # mean grayscale below this => too dark
BRIGHT_THRESHOLD = 225.0    # mean grayscale above this => overexposed
MIN_SIDE = 160              # pixels


def preprocess_for_classifier(img: Image.Image, size: int = 224, mean=None, std=None) -> np.ndarray:
    """Resize (short side -> size*1.14, centre crop), scale to [0,1], ImageNet-normalise.

    Returns float32 array shaped (1, 3, size, size). Configure mean/std per model if yours differs.
    """
    resize_to = int(round(size * 1.14))
    w, h = img.size
    scale = resize_to / min(w, h)
    img = img.resize((max(size, round(w * scale)), max(size, round(h * scale))), Image.BICUBIC)
    left = (img.width - size) // 2
    top = (img.height - size) // 2
    img = img.crop((left, top, left + size, top + size))
    arr = np.asarray(img, dtype=np.float32) / 255.0
    m = IMAGENET_MEAN if mean is None else np.asarray(mean, dtype=np.float32)
    sd = IMAGENET_STD if std is None else np.asarray(std, dtype=np.float32)
    arr = (arr - m) / sd
    return np.transpose(arr, (2, 0, 1))[None, ...].astype(np.float32)


def pil_to_bgr(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.asarray(img.convert("RGB")), cv2.COLOR_RGB2BGR)


def bgr_to_pil(frame: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))


def quality_report(bgr: np.ndarray) -> dict:
    """Deterministic image-quality metrics + human-readable warnings."""
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    blur = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    brightness = float(gray.mean())
    warnings: list[str] = []
    if min(h, w) < MIN_SIDE:
        warnings.append(f"Low resolution ({w}x{h}px). Use an image with at least {MIN_SIDE}px on the short side.")
    if blur < BLUR_THRESHOLD:
        warnings.append("The image looks blurry, so fine surface detail cannot be assessed.")
    if brightness < DARK_THRESHOLD:
        warnings.append("The image is very dark; colour and surface cues are unreliable.")
    if brightness > BRIGHT_THRESHOLD:
        warnings.append("The image is overexposed; colour and surface cues are unreliable.")
    return {
        "width": int(w), "height": int(h),
        "sharpness": round(blur, 1), "brightness": round(brightness, 1),
        "warnings": warnings, "usable": not warnings,
    }


def to_jpeg_b64(img: Image.Image, max_side: int = 1024, quality: int = 85) -> str:
    img = img.copy()
    img.thumbnail((max_side, max_side))
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def bgr_to_jpeg_b64(frame: np.ndarray, max_side: int = 1024, quality: int = 80) -> str:
    return to_jpeg_b64(bgr_to_pil(frame), max_side=max_side, quality=quality)
