"""Food recognition: provider selection + orchestration with nutrition estimation.

Result `recognition.source` is one of: "onnx_model", "llm_vision", "user_selected".
When no provider is available the result has status "unavailable" and NO prediction is invented;
the UI lets the user choose the food manually (source "user_selected").
"""
from __future__ import annotations

import asyncio
import logging

from PIL import Image

from app.config import Settings
from app.services import nutrition
from app.services.llm import LLM, extract_json, has_vision
from app.services.onnx_classifier import OnnxImageClassifier
from app.utils.errors import ProviderError, ProviderUnavailable
from app.utils.imaging import to_jpeg_b64

log = logging.getLogger("foodverse.food")

LLM_SYSTEM = ("You identify food in photos for a nutrition app. Respond with JSON only: "
              '{"items":[{"name":"<common food name>"}], "notes":"<short caveat>"}. '
              "List at most 4 distinct foods you can actually see. Do not guess hidden ingredients. "
              "If there is no food, return an empty items list.")


class FoodRecognizer:
    def __init__(self, settings: Settings, llm: LLM, onnx: OnnxImageClassifier | None = None):
        self.s, self.llm = settings, llm
        self.onnx = onnx or OnnxImageClassifier(settings.food_model_path, settings.food_labels_path,
                                                settings.food_model_input_size, name="food-onnx",
                                                mean=settings.food_model_mean, std=settings.food_model_std)

    def provider(self) -> str:
        pref = self.s.vision_provider
        if pref in ("auto", "onnx") and self.onnx.available:
            return "onnx"
        if pref in ("auto", "llm") and has_vision(self.llm):
            return "llm"
        return "none"

    async def recognize(self, img: Image.Image) -> dict:
        prov = self.provider()
        if prov == "none":
            return {"status": "unavailable", "source": None, "items": [],
                    "message": ("No food-recognition model is configured. Add ONNX weights or an LLM key "
                                "(see README), or choose the food manually below.")}
        if prov == "onnx":
            preds = await asyncio.to_thread(self.onnx.classify, img, 3)
            items = []
            for p in preds:
                key = nutrition.find_food(p["label"].replace("_", " "))
                items.append({"label": p["label"], "confidence": p["confidence"],
                              "confidence_kind": "softmax probability (uncalibrated)", "food_key": key})
            return {"status": "ok", "source": "onnx_model", "model": self.onnx.name, "items": items, "message": None}
        # LLM vision
        raw = await self.llm.complete(LLM_SYSTEM, [{"role": "user", "content": "What food is in this image?"}],
                                      images_b64=[to_jpeg_b64(img)], max_tokens=1200)
        data = extract_json(raw)
        if not isinstance(data, dict):
            raise ProviderError("The AI model returned an unexpected structure.")
        names = [str(i.get("name", "")).strip() for i in (data.get("items") or []) if isinstance(i, dict) and i.get("name")]
        items = [{"label": n, "confidence": None, "confidence_kind": "not provided by this model",
                  "food_key": nutrition.find_food(n)} for n in names[:4]]
        return {"status": "ok" if items else "no_food_detected", "source": "llm_vision", "model": self.s.llm_model,
                "items": items, "message": (data.get("notes") if isinstance(data.get("notes"), str) else None) or ("No food was identified in this image." if not items else None)}

    async def analyze(self, img: Image.Image, grams: float | None = None) -> dict:
        try:
            rec = await self.recognize(img)
        except (ProviderUnavailable, ProviderError) as exc:
            log.warning("Food recognition failed: %s", exc.message)
            rec = {"status": "error", "source": None, "items": [], "message": exc.message}
        analyses, unmatched = [], []
        for it in rec["items"]:
            if it.get("food_key"):
                est = nutrition.estimate(key=it["food_key"], grams=grams if len(rec["items"]) == 1 else None)
                est["prediction"] = {"label": it["label"], "confidence": it["confidence"],
                                     "confidence_kind": it["confidence_kind"], "source": rec["source"]}
                analyses.append(est)
            else:
                unmatched.append(it["label"])
        return {"recognition": rec, "analyses": analyses, "unmatched_labels": unmatched,
                "notes": ["Predicted food (model) and nutrition facts (reference table) are separate: "
                          "the table has no information about this specific plate."]}

    def manual(self, key_or_label: str, grams: float | None) -> dict:
        est = nutrition.estimate(key_or_label, grams=grams)
        est["prediction"] = {"label": est["food_name"], "confidence": None, "confidence_kind": "user selected", "source": "user_selected"}
        return {"recognition": {"status": "ok", "source": "user_selected", "items": [], "message": None},
                "analyses": [est], "unmatched_labels": [], "notes": ["Food chosen by you; no image model was used."]}
