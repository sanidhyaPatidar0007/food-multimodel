"""Generic ONNX image classifier (real inference when weights are present).

Expected model: input (1,3,H,W) float32, ImageNet-normalised; output = logits or probabilities
of shape (1, N). Labels file: one label per line, same order as the output.
Replace/adapt `preprocess` if your model was trained with different normalisation.
"""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PIL import Image

from app.utils.errors import ProviderError, ProviderUnavailable
from app.utils.imaging import preprocess_for_classifier

log = logging.getLogger("foodverse.onnx")


def softmax(x: np.ndarray) -> np.ndarray:
    x = x - x.max()
    e = np.exp(x)
    return e / e.sum()


class OnnxImageClassifier:
    def __init__(self, model_path: str, labels_path: str, input_size: int = 224, name: str = "onnx", mean=None, std=None):
        self.model_path, self.labels_path = Path(model_path), Path(labels_path)
        self.input_size, self.name, self.mean, self.std = input_size, name, mean, std
        self._session = None
        self._labels: list[str] = []

    @property
    def available(self) -> bool:
        return self.model_path.is_file() and self.labels_path.is_file()

    def _load(self) -> None:
        if self._session is not None:
            return
        if not self.available:
            raise ProviderUnavailable(f"Model weights not found at {self.model_path}. See README 'Adding model weights'.")
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise ProviderUnavailable("onnxruntime is not installed.") from exc
        self._labels = [l.strip() for l in self.labels_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        self._session = ort.InferenceSession(str(self.model_path), providers=["CPUExecutionProvider"])
        log.info("Loaded ONNX model %s (%d labels)", self.model_path.name, len(self._labels))

    def classify(self, img: Image.Image, top_k: int = 3) -> list[dict]:
        """Blocking. Call through asyncio.to_thread from async code."""
        self._load()
        x = preprocess_for_classifier(img, self.input_size, self.mean, self.std)
        try:
            inp = self._session.get_inputs()[0].name
            out = np.asarray(self._session.run(None, {inp: x})[0]).reshape(-1)
        except Exception as exc:  # onnxruntime raises various types
            raise ProviderError("Model inference failed.") from exc
        if out.shape[0] != len(self._labels):
            raise ProviderError(f"Model outputs {out.shape[0]} classes but labels file has {len(self._labels)}.")
        probs = out if (out.min() >= 0 and abs(out.sum() - 1) < 1e-3) else softmax(out)
        idx = np.argsort(probs)[::-1][:top_k]
        return [{"label": self._labels[i], "confidence": round(float(probs[i]), 4)} for i in idx]
