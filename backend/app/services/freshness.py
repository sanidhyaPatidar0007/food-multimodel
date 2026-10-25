"""Freshness / spoilage assessment.

Three analysers behind one interface, in priority order:
  1. OnnxImageClassifier (if FRESHNESS_MODEL_PATH exists) -> kind "trained_model".
  2. A vision LLM (if configured) -> kind "llm_vision". It looks at the actual photo; its verdict is clamped by
     the same safety rules below, and its output is never trusted blindly.
  3. ColorHeuristicBaseline (OpenCV colour/texture statistics) -> kind "heuristic_baseline".
     This is NOT a trained model: no confidence score is reported and the UI labels it "demo baseline".

Hard safety rules enforced in `assess`:
  * Never returns "safe". The most positive verdict is "no_visible_deterioration".
  * Image-quality problems => "uncertain".
  * High-risk categories (meat, fish, dairy, cooked_meal) can never receive a positive visual verdict.
  * The colour heuristic cannot separate food from a dark table or several dishes, so for "cooked_meal"/"other"
    it never reports deterioration on its own: the answer is "uncertain".
"""
from __future__ import annotations

import asyncio
import logging

import cv2
import numpy as np
from PIL import Image

from app.config import Settings
from app.services.llm import LLM, extract_json, has_vision
from app.services.onnx_classifier import OnnxImageClassifier
from app.utils.errors import ProviderError, ProviderUnavailable
from app.utils.imaging import pil_to_bgr, quality_report, to_jpeg_b64

log = logging.getLogger("foodverse.freshness")

CATEGORIES = ["fruit", "vegetable", "bread", "meat", "fish", "dairy", "cooked_meal", "other"]
HIGH_RISK = {"meat", "fish", "dairy", "cooked_meal"}
VERDICTS = {
    "no_visible_deterioration": "No visible signs of deterioration",
    "signs_of_deterioration": "Signs of deterioration",
    "uncertain": "Uncertain",
}
# Heuristic thresholds (fractions of the analysed food region). Tuned for a coarse demo, not validated.
DARK_SPOT_HI, DARK_SPOT_LO = 0.12, 0.03
BROWN_HI, BROWN_LO = 0.35, 0.10
PALE_HI, PALE_LO = 0.10, 0.02
MIN_FOOD_FRACTION = 0.08


def extract_features(bgr: np.ndarray) -> dict:
    """Colour/texture statistics over the likely food region (centre crop, background excluded).

    The food region is the *filled* outline of saturated, mid-brightness pixels, so dark spots and
    pale patches enclosed by food are analysed instead of being mistaken for background.
    """
    h, w = bgr.shape[:2]
    my, mx = int(h * 0.1), int(w * 0.1)
    crop = cv2.resize(bgr[my:h - my, mx:w - mx], (256, 256), interpolation=cv2.INTER_AREA)
    hsv = cv2.cvtColor(cv2.GaussianBlur(crop, (5, 5), 0), cv2.COLOR_BGR2HSV)
    H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    core = ((S > 35) & (V > 35) & (V < 250)).astype(np.uint8)
    core = cv2.morphologyEx(core, cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
    contours, _ = cv2.findContours(core, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(core)
    min_area = 0.02 * core.size
    for c in contours:
        if cv2.contourArea(c) >= min_area:
            cv2.drawContours(filled, [c], -1, 1, thickness=cv2.FILLED)
    filled_b = filled.astype(bool)
    area = int(filled_b.sum())
    fraction = area / filled.size
    zero = {"food_fraction": round(fraction, 3), "dark_spot_fraction": 0.0, "brown_fraction": 0.0,
            "pale_patch_fraction": 0.0, "texture_variance": 0.0, "mean_saturation": 0.0}
    if area < 50:
        return zero
    interior = cv2.erode(filled, np.ones((9, 9), np.uint8)).astype(bool)  # ignore edge pixels
    dark = filled_b & (V < 70)
    brown = filled_b & (H >= 8) & (H <= 22) & (S > 60) & (V < 170)
    pale = interior & (S < 45) & (V > 170)
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    tex = float(cv2.Laplacian(gray, cv2.CV_64F)[filled_b].var())
    return {
        "food_fraction": round(fraction, 3),
        "dark_spot_fraction": round(float(dark.sum()) / area, 3),
        "brown_fraction": round(float(brown.sum()) / area, 3),
        "pale_patch_fraction": round(float(pale.sum()) / area, 3),
        "texture_variance": round(tex, 1),
        "mean_saturation": round(float(S[filled_b].mean()), 1),
    }


def _heuristic_signals(f: dict, category: str) -> tuple[list[dict], int]:
    """Return (evidence list, count of 'strong' signals)."""
    ev, strong = [], 0

    def rule(name: str, val: float, lo: float, hi: float, text_hi: str, text_mid: str):
        nonlocal strong
        if val >= hi:
            strong += 1
            ev.append({"feature": name, "value": val, "level": "strong", "observation": text_hi})
        elif val >= lo:
            ev.append({"feature": name, "value": val, "level": "mild", "observation": text_mid})
        else:
            ev.append({"feature": name, "value": val, "level": "none", "observation": "Within the range this baseline treats as typical."})

    rule("dark_spot_fraction", f["dark_spot_fraction"], DARK_SPOT_LO, DARK_SPOT_HI,
         "Large share of very dark pixels (possible rot, bruising or shadow).", "Some dark areas (could be bruising or just shadow).")
    brown_hi = BROWN_HI + (0.25 if category in {"bread", "cooked_meal"} else 0)  # browning is normal for crusts
    rule("brown_fraction", f["brown_fraction"], BROWN_LO, brown_hi,
         "Large share of brown tones (possible oxidation or decay; normal for some foods).", "Some brown tones.")
    rule("pale_patch_fraction", f["pale_patch_fraction"], PALE_LO, PALE_HI,
         "Pale, low-colour patches that can resemble mould (also caused by glare or flour).", "Small pale patches (possible glare).")
    return ev, strong


LLM_SYSTEM = (
    "You give a cautious VISUAL freshness opinion on a food photo for a kitchen app. Judge only what is clearly visible: "
    "mould (fuzzy or powdery patches), slime or wet sheen on meat/fish, dark rotten or mushy areas, severe wilting or "
    "shrivelling, unusual discolouration. Ignore the background, plates, shadows, sauces and normal browning of cooked "
    "or baked food. You cannot judge safety, smell or bacteria. Respond with JSON only: "
    '{"verdict":"no_visible_deterioration|signs_of_deterioration|uncertain",'
    '"observations":[{"item":"<food or area>","finding":"<what you can see>","concern":"none|mild|strong"}],'
    '"image_problem":"<why the photo is hard to judge, or empty>"}. '
    "Use signs_of_deterioration only when you can point to a specific visible sign. Use uncertain when the photo is "
    "unclear, several foods are mixed, or you are not sure. Never say the food is safe."
)


class FreshnessService:
    def __init__(self, settings: Settings, model: OnnxImageClassifier | None = None, llm: LLM | None = None):
        self.llm = llm
        self.model = model or OnnxImageClassifier(settings.freshness_model_path, settings.freshness_labels_path, name="freshness-onnx",
                                                          mean=settings.freshness_model_mean, std=settings.freshness_model_std)

    @property
    def mode(self) -> str:
        if self.model.available:
            return "trained_model"
        return "llm_vision" if self.llm is not None and has_vision(self.llm) else "baseline_demo"

    async def assess(self, img: Image.Image, category: str = "other") -> dict:
        if category not in CATEGORIES:
            category = "other"
        bgr = pil_to_bgr(img)
        quality = quality_report(bgr)
        feats = await asyncio.to_thread(extract_features, bgr)
        warnings = list(quality["warnings"])
        if feats["food_fraction"] < MIN_FOOD_FRACTION:
            warnings.append("The food could not be isolated from the background; show the item larger and well lit.")
        reliable = not warnings

        if self.model.available:
            return await self._assess_model(img, category, feats, quality, warnings)

        llm_note: str | None = None
        reasons_pre: list[str] = []
        if self.llm is not None and has_vision(self.llm):
            try:
                return await self._assess_llm(img, category, feats, quality, warnings)
            except (ProviderUnavailable, ProviderError) as exc:
                log.warning("LLM freshness assessment failed, using colour baseline: %s", exc.message)
                llm_note = f"The AI vision check failed ({exc.message}), so the simpler colour baseline was used instead."

        evidence, strong = _heuristic_signals(feats, category)
        mild = sum(1 for e in evidence if e["level"] == "mild")
        if strong >= 1 and feats["food_fraction"] >= MIN_FOOD_FRACTION:
            verdict = "signs_of_deterioration"
            if category in {"cooked_meal", "other"}:
                # Dark plates/tables, sauces, herbs and several dishes all look like "dark spots" to a colour count.
                verdict = "uncertain"
                reasons_pre = ["Colour statistics cannot tell spoilage from dark plates, sauces, herbs or mixed dishes, so no "
                               "deterioration verdict is given for this category. Configure a vision model for a better check."]
        elif not reliable or mild >= 1:
            verdict = "uncertain"
        else:
            verdict = "no_visible_deterioration"
        reasons: list[str] = list(reasons_pre)
        if llm_note:
            reasons.append(llm_note)
        if verdict == "no_visible_deterioration" and category in HIGH_RISK:
            verdict = "uncertain"
            reasons.append(f"Spoilage of {category.replace('_', ' ')} cannot be judged from colour alone, so no positive verdict is given.")
        if category == "other":
            reasons.append("No food category was selected, so category-specific cues were not applied.")
        return self._result(verdict, category, "heuristic_baseline", "opencv-color-heuristic-v0", False,
                            feats, evidence, quality, warnings, reasons, confidence=None)

    async def _assess_llm(self, img, category, feats, quality, warnings) -> dict:
        label = f"Food category chosen by the user: {category.replace('_', ' ')}."
        raw = await self.llm.complete(LLM_SYSTEM, [{"role": "user", "content": label + " Assess the photo."}],
                                      images_b64=[to_jpeg_b64(img)], max_tokens=2500)
        data = extract_json(raw)
        if not isinstance(data, dict):
            raise ProviderError("The AI model returned an unexpected structure.")
        verdict = data.get("verdict") if data.get("verdict") in VERDICTS else "uncertain"
        reasons: list[str] = []
        evidence = []
        for o in (data.get("observations") or [])[:8]:
            if not isinstance(o, dict):
                continue
            concern = o.get("concern") if o.get("concern") in ("none", "mild", "strong") else "none"
            evidence.append({"feature": str(o.get("item") or "observation")[:60], "value": 0.0,
                             "level": {"none": "observed", "mild": "mild", "strong": "strong"}[concern],
                             "observation": str(o.get("finding") or "")[:300]})
        # --- safety clamps, applied in code regardless of what the model said ---
        if verdict == "signs_of_deterioration" and not any(e["level"] in ("mild", "strong") for e in evidence):
            verdict = "uncertain"   # a deterioration claim must point to a specific visible sign
            reasons.append("The AI did not point to a specific visible sign, so the result was downgraded to uncertain.")
        if verdict == "no_visible_deterioration" and (warnings or str(data.get("image_problem") or "").strip()):
            verdict = "uncertain"
        if verdict == "no_visible_deterioration" and category in HIGH_RISK:
            verdict = "uncertain"
            reasons.append(f"Spoilage of {category.replace('_', ' ')} cannot be judged from a photo, so no positive verdict is given.")
        if isinstance(data.get("image_problem"), str) and data["image_problem"].strip():
            warnings = [*warnings, data["image_problem"].strip()[:200]]
        if category == "other":
            reasons.append("No food category was selected, so category-specific cues were not applied.")
        name = getattr(self.llm.s, "llm_vision_model", None) if hasattr(self.llm, "s") else None
        return self._result(verdict, category, "llm_vision", name or "vision-llm", True, feats, evidence, quality, warnings, reasons,
                            confidence=None, model_label="AI vision model opinion - not a validated or calibrated classifier")

    async def _assess_model(self, img, category, feats, quality, warnings) -> dict:
        try:
            preds = await asyncio.to_thread(self.model.classify, img, 3)
        except (ProviderUnavailable, ProviderError) as exc:
            raise exc
        top = preds[0]
        label = top["label"].lower()
        verdict = ("signs_of_deterioration" if any(k in label for k in ("rot", "spoil", "stale", "bad", "mold", "mould"))
                   else "no_visible_deterioration" if any(k in label for k in ("fresh", "good")) else "uncertain")
        if warnings or top["confidence"] < 0.6:
            verdict = "uncertain" if verdict == "no_visible_deterioration" else verdict
        if verdict == "no_visible_deterioration" and category in HIGH_RISK:
            verdict = "uncertain"
        evidence = [{"feature": "model_top_prediction", "value": p["confidence"], "level": "model", "observation": p["label"]} for p in preds]
        return self._result(verdict, category, "trained_model", self.model.name, True, feats, evidence, quality, warnings, [],
                            confidence={"value": top["confidence"], "kind": "softmax probability (uncalibrated)"})

    @staticmethod
    def _result(verdict, category, kind, model_name, trained, feats, evidence, quality, warnings, reasons, confidence,
                model_label: str | None = None) -> dict:
        discard = verdict == "signs_of_deterioration"
        recs = ["Visual checks cannot show whether food is microbiologically safe. When in doubt, throw it out.",
                "Check use-by / best-before dates and how long the food has been stored.",
                "Smell and texture changes (sliminess, off odours) are further warning signs this tool cannot see."]
        if discard:
            recs.insert(0, "Discard this item or the affected portion according to safe-handling guidance; do not taste-test it.")
        if category in HIGH_RISK:
            recs.append("Meat, fish, dairy and cooked leftovers can be unsafe without any visible change: refrigerate promptly and follow date labels.")
        if category in {"fruit", "vegetable"} and not discard:
            recs.append("Store produce in a cool, dry place or the fridge as appropriate and wash before eating.")
        return {
            "verdict": verdict, "verdict_label": VERDICTS[verdict], "category": category,
            "confidence": confidence,
            "model": {"name": model_name, "kind": kind, "trained": trained,
                      "label": model_label or ("Trained classifier" if trained else "Demo baseline (colour heuristics) - not a trained AI model")},
            "mode": "trained_model" if trained else "baseline_demo",
            "evidence": evidence, "features": feats, "image_quality": quality,
            "warnings": warnings, "reasons": reasons, "recommendations": recs,
            "safety_notice": ("This is a visual assessment only. It cannot detect bacteria, toxins or other hazards, "
                              "and a fresh appearance does not mean food is safe to eat."),
        }
