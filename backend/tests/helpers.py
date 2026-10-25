"""Shared test helpers (framework-free)."""
from __future__ import annotations

import io
import os
import tempfile

import cv2
import numpy as np
from PIL import Image, ImageDraw

from app.config import Settings


def make_image_bytes(fmt: str = "PNG", size=(320, 320), color=(190, 40, 40), circle: bool = True) -> bytes:
    img = Image.new("RGB", size, (245, 245, 245))
    if circle:
        ImageDraw.Draw(img).ellipse((40, 40, size[0] - 40, size[1] - 40), fill=color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def make_video_bytes(seconds: int = 6, fps: int = 10, size=(320, 240)) -> bytes:
    fd, path = tempfile.mkstemp(suffix=".avi")
    os.close(fd)
    try:
        vw = cv2.VideoWriter(path, cv2.VideoWriter_fourcc(*"MJPG"), fps, size)
        rng = np.random.default_rng(1)
        for _ in range(seconds * fps):
            vw.write(rng.normal(128, 40, (size[1], size[0], 3)).clip(0, 255).astype("uint8"))
        vw.release()
        with open(path, "rb") as fh:
            return fh.read()
    finally:
        os.remove(path)


def make_settings(**kw) -> Settings:
    base = dict(database_path=":memory:", llm_provider="none", llm_api_key="", vision_provider="auto",
                food_model_path="/nonexistent/food.onnx", food_labels_path="/nonexistent/labels.txt",
                freshness_model_path="/nonexistent/fresh.onnx", freshness_labels_path="/nonexistent/fl.txt")
    base.update(kw)
    return Settings(**base)


class FakeLLM:
    """Deterministic stand-in for an LLM provider."""
    name = "fake"

    def __init__(self, response: str = "", error: Exception | None = None, available: bool = True):
        self.response, self.error, self._available, self.calls = response, error, available, []

    @property
    def available(self) -> bool:
        return self._available

    async def complete(self, system, messages, *, images_b64=None, max_tokens=1500):
        self.calls.append({"system": system, "messages": messages, "images": images_b64})
        if self.error:
            raise self.error
        return self.response


class FakeOnnx:
    """Stand-in for a trained classifier: returns fixed predictions."""
    name = "fake-onnx"

    def __init__(self, preds):
        self.preds, self.available = preds, True

    def classify(self, img, top_k=3):
        return self.preds[:top_k]


def make_textured_image_bytes(fmt: str = "PNG", size=(400, 400)) -> bytes:
    """Noisy image that passes the sharpness/brightness quality gates (flat synthetic images do not)."""
    arr = np.random.default_rng(7).normal(128, 45, (size[1], size[0], 3)).clip(0, 255).astype("uint8")
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, format=fmt)
    return buf.getvalue()
