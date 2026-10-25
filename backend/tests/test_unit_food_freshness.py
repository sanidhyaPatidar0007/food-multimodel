import asyncio

import numpy as np
import pytest
from PIL import Image, ImageDraw

from app.services.food_recognition import FoodRecognizer
from app.services.freshness import FreshnessService
from app.services.llm import build_llm
from app.utils.errors import ProviderError

from tests.helpers import FakeLLM, FakeOnnx, make_image_bytes, make_settings
from app.utils.media import validate_image_bytes


def img(**kw):
    return validate_image_bytes(make_image_bytes("PNG", **kw), 10**7)


def test_food_unavailable_when_no_provider_and_no_fake_prediction():
    fr = FoodRecognizer(make_settings(), build_llm(make_settings()))
    res = asyncio.run(fr.analyze(img()))
    assert res["recognition"]["status"] == "unavailable"
    assert res["recognition"]["source"] is None and res["analyses"] == []


def test_food_onnx_response_structure_and_separation_of_prediction_and_database():
    fr = FoodRecognizer(make_settings(), FakeLLM(available=False), onnx=FakeOnnx(
        [{"label": "pizza", "confidence": 0.81}, {"label": "mystery_dish", "confidence": 0.1}]))
    res = asyncio.run(fr.analyze(img()))
    assert res["recognition"]["source"] == "onnx_model" and res["recognition"]["status"] == "ok"
    a = res["analyses"][0]
    assert a["prediction"]["confidence"] == 0.81 and a["prediction"]["source"] == "onnx_model"
    assert a["source"]["kind"] == "database"            # nutrition facts come from the table, not the model
    assert {"nutrition", "health", "uncertainty", "portion"} <= set(a)
    assert res["unmatched_labels"] == ["mystery_dish"]


def test_food_llm_vision_has_no_fabricated_confidence():
    llm = FakeLLM('{"items":[{"name":"banana"}],"notes":""}')
    fr = FoodRecognizer(make_settings(llm_provider="anthropic", llm_api_key="x", vision_provider="llm"), llm,
                        onnx=FakeOnnx([]))
    fr.onnx.available = False
    res = asyncio.run(fr.analyze(img()))
    assert res["analyses"][0]["prediction"]["confidence"] is None


def test_food_provider_error_degrades_gracefully():
    llm = FakeLLM(error=ProviderError("The AI provider timed out. Please try again."))
    fr = FoodRecognizer(make_settings(llm_provider="anthropic", llm_api_key="x", vision_provider="llm"), llm)
    res = asyncio.run(fr.analyze(img()))
    assert res["recognition"]["status"] == "error" and "timed out" in res["recognition"]["message"]


def test_manual_food_selection_is_labelled_user_selected():
    fr = FoodRecognizer(make_settings(), build_llm(make_settings()))
    res = fr.manual("pizza", 150)
    assert res["analyses"][0]["prediction"]["source"] == "user_selected"


# ---- freshness ----
rng = np.random.default_rng(0)


def fruit(spots=0, brown=False):
    im = Image.new("RGB", (400, 400), (245, 245, 245))
    ImageDraw.Draw(im).ellipse((60, 60, 340, 340), fill=(120, 70, 30) if brown else (190, 40, 40))
    arr = np.array(im).astype(int) + rng.normal(0, 14, (400, 400, 3))
    im = Image.fromarray(np.clip(arr, 0, 255).astype("uint8"))
    d = ImageDraw.Draw(im)
    for _ in range(spots):
        x, y = (int(v) for v in rng.integers(100, 300, 2))
        d.ellipse((x, y, x + 40, y + 40), fill=(25, 15, 10))
    return im


SVC = FreshnessService(make_settings())


def test_freshness_baseline_is_labelled_not_trained_and_has_no_confidence():
    r = asyncio.run(SVC.assess(fruit(), "fruit"))
    assert r["mode"] == "baseline_demo" and r["model"]["trained"] is False
    assert "not a trained" in r["model"]["label"].lower()
    assert r["confidence"] is None


def test_freshness_never_claims_safe():
    for im, cat in [(fruit(), "fruit"), (fruit(), "meat"), (fruit(brown=True), "fruit")]:
        r = asyncio.run(SVC.assess(im, cat))
        assert r["verdict"] in {"no_visible_deterioration", "signs_of_deterioration", "uncertain"}
        assert "safe" not in r["verdict"].replace("unsafe", "")
        assert "does not mean food is safe" in r["safety_notice"]
        assert any("throw it out" in x for x in r["recommendations"])


def test_freshness_high_risk_categories_get_no_positive_verdict():
    for cat in ("meat", "fish", "dairy", "cooked_meal"):
        r = asyncio.run(SVC.assess(fruit(), cat))
        assert r["verdict"] != "no_visible_deterioration"


def test_freshness_uncertain_on_poor_quality_image():
    dark = Image.new("RGB", (300, 300), (10, 10, 10))
    r = asyncio.run(SVC.assess(dark, "fruit"))
    assert r["verdict"] == "uncertain" and r["warnings"]
    tiny_blur = Image.new("RGB", (100, 100), (190, 40, 40))
    r2 = asyncio.run(SVC.assess(tiny_blur, "fruit"))
    assert r2["verdict"] == "uncertain"


def test_freshness_flags_obvious_browning_and_unknown_category_falls_back():
    r = asyncio.run(SVC.assess(fruit(brown=True), "fruit"))
    assert r["verdict"] == "signs_of_deterioration"
    assert any("discard" in x.lower() for x in r["recommendations"])
    assert asyncio.run(SVC.assess(fruit(), "not-a-category"))["category"] == "other"
