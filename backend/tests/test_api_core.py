"""API integration tests. Mocked providers only. Requires: pip install -r requirements-dev.txt"""
import json

import pytest

from tests.helpers import FakeLLM, make_image_bytes, make_textured_image_bytes, make_video_bytes

pytestmark = pytest.mark.api
V1 = "/api/v1"


def png(**kw):
    return ("food.png", make_image_bytes("PNG", **kw), "image/png")


def test_startup_and_health(client):
    r = client.get(f"{V1}/health")
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["status"] == "ok" and d["database"] is True
    assert d["providers"]["llm"]["configured"] is False
    assert "api_key" not in json.dumps(d).lower()
    assert r.headers["x-request-id"]


def test_openapi_docs_available(client):
    spec = client.get("/openapi.json").json()
    assert f"{V1}/food/analyze" in spec["paths"] and f"{V1}/meal-planner/generate" in spec["paths"]


def test_unknown_route_uses_error_envelope(client):
    r = client.get(f"{V1}/nope")
    assert r.status_code == 404 and r.json()["ok"] is False and r.json()["error"]["code"] == "http_error"


def test_cors_allows_configured_origin_only(make_client):
    c = make_client(cors_origins=["http://localhost:5173"])
    ok = c.get(f"{V1}/health", headers={"Origin": "http://localhost:5173"})
    bad = c.get(f"{V1}/health", headers={"Origin": "http://evil.example"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in bad.headers


def test_unhandled_errors_do_not_leak_details(make_client):
    c = make_client(raise_server_exceptions=False)
    @c.app.get("/boom")
    async def boom():
        raise RuntimeError("secret-token-123")
    r = c.get("/boom")
    assert r.status_code == 500
    assert "secret-token-123" not in r.text and "Traceback" not in r.text and r.json()["error"]["code"] == "internal_error"


# ---------- uploads ----------

def test_food_analyze_without_provider_returns_unavailable_not_a_fake_prediction(client):
    r = client.post(f"{V1}/food/analyze", files={"file": png()})
    assert r.status_code == 200
    d = r.json()["data"]
    assert d["recognition"]["status"] == "unavailable" and d["analyses"] == []


@pytest.mark.parametrize("fmt,mime", [("JPEG", "image/jpeg"), ("PNG", "image/png"), ("WEBP", "image/webp")])
def test_supported_image_types_accepted(client, fmt, mime):
    r = client.post(f"{V1}/food/analyze", files={"file": ("x", make_image_bytes(fmt), mime)})
    assert r.status_code == 200


def test_unsupported_empty_corrupt_and_oversize_uploads(make_client):
    c = make_client(max_image_mb=0.05)
    assert c.post(f"{V1}/food/analyze", files={"file": ("a.gif", make_image_bytes("GIF"), "image/gif")}).status_code == 415
    assert c.post(f"{V1}/food/analyze", files={"file": ("a.png", b"", "image/png")}).status_code == 422
    assert c.post(f"{V1}/food/analyze", files={"file": ("a.png", b"\x89PNG\r\n\x1a\n" + b"junk" * 20, "image/png")}).status_code == 422
    big = c.post(f"{V1}/food/analyze", files={"file": ("a.png", make_image_bytes("PNG", size=(1500, 1500), color=(1, 2, 3)) + b"\0" * 80_000, "image/png")})
    assert big.status_code == 413 and big.json()["error"]["code"] == "payload_too_large"


def test_missing_file_is_validation_error(client):
    r = client.post(f"{V1}/food/analyze")
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_food_manual_and_unknown_food(client):
    r = client.post(f"{V1}/food/manual", json={"label": "pizza", "grams": 120})
    d = r.json()["data"]["analyses"][0]
    assert r.status_code == 200 and d["prediction"]["source"] == "user_selected" and d["source"]["kind"] == "database"
    assert client.post(f"{V1}/food/manual", json={"label": "qqqqzzzz"}).status_code == 400
    assert client.post(f"{V1}/food/manual", json={"label": "pizza", "grams": 99999}).status_code == 422
    assert client.post(f"{V1}/food/manual", content="not json", headers={"content-type": "application/json"}).status_code == 422


def test_food_analyze_with_mocked_llm_vision(make_client):
    llm = FakeLLM('{"items":[{"name":"pizza"}],"notes":""}')
    c = make_client(llm=llm, llm_provider="anthropic", llm_api_key="x", vision_provider="llm")
    d = c.post(f"{V1}/food/analyze", files={"file": png()}).json()["data"]
    assert d["recognition"]["source"] == "llm_vision" and d["analyses"][0]["food_key"] == "pizza"
    assert llm.calls and llm.calls[0]["images"]


# ---------- freshness ----------

def test_freshness_endpoint_structure_and_safety_fields(client):
    r = client.post(f"{V1}/freshness/analyze", files={"file": png()}, data={"category": "fruit"})
    d = r.json()["data"]
    assert r.status_code == 200 and d["mode"] == "baseline_demo" and d["confidence"] is None
    assert d["verdict"] in ("no_visible_deterioration", "signs_of_deterioration", "uncertain")
    assert d["safety_notice"] and d["recommendations"]


def test_freshness_bad_category_and_dark_image(client):
    assert client.post(f"{V1}/freshness/analyze", files={"file": png()}, data={"category": "unicorn"}).status_code == 400
    dark = ("d.png", make_image_bytes("PNG", color=(5, 5, 5), circle=False), "image/png")
    d = client.post(f"{V1}/freshness/analyze", files={"file": dark}).json()["data"]
    assert d["verdict"] == "uncertain" and d["warnings"]


# ---------- hygiene ----------

def vid(seconds=6):
    return ("k.avi", make_video_bytes(seconds), "video/x-msvideo")


def test_hygiene_video_without_detector_reports_not_assessed(client):
    d = client.post(f"{V1}/hygiene/analyze", files=[("files", vid())]).json()["data"]
    assert d["status"] == "detector_unavailable" and d["score"]["score"] is None
    assert all(c["status"] == "not_assessed" for c in d["criteria"].values()) and d["previews"]


def test_hygiene_frame_preview_and_interval(client):
    d = client.post(f"{V1}/hygiene/frames", files=[("files", vid())], data={"interval_seconds": "3"}).json()["data"]
    assert [f["timestamp_s"] for f in d["frames"]] == [0.0, 3.0] and d["frames"][0]["jpeg_b64"]


def test_hygiene_invalid_inputs(client):
    assert client.post(f"{V1}/hygiene/analyze", files=[("files", ("v.mp4", b"\x00\x00\x00\x18ftypmp42" + b"junk" * 50, "video/mp4"))]).status_code == 422
    assert client.post(f"{V1}/hygiene/analyze", files=[("files", ("v.txt", b"hello world", "text/plain"))]).status_code in (415, 422)
    assert client.post(f"{V1}/hygiene/analyze", files=[("files", vid())], data={"config": "{not json"}).status_code == 400
    assert client.post(f"{V1}/hygiene/analyze", files=[("files", vid())], data={"config": json.dumps({"weights": {"bogus": 1}})}).status_code == 422
    assert client.post(f"{V1}/hygiene/analyze").status_code == 422


def test_hygiene_images_with_mocked_vision(make_client):
    reply = {"frames": [{"index": 0, "findings": [{"criterion": "hair_covering", "status": "violation", "severity": "high", "evidence": "no cap"},
                                                  {"criterion": "surface_cleanliness", "status": "pass", "severity": "low", "evidence": "clean"},
                                                  {"criterion": "protective_equipment", "status": "pass", "severity": "low", "evidence": "gloves"}]}]}
    c = make_client(llm=FakeLLM(json.dumps(reply)), llm_provider="anthropic", llm_api_key="x")
    busy = ("a.png", make_textured_image_bytes("PNG"), "image/png")
    d = c.post(f"{V1}/hygiene/analyze", files=[("files", busy)]).json()["data"]
    assert d["detector"] == "llm_vision" and d["issues"][0]["criterion"] == "hair_covering" and d["score"]["score"] is not None


# ---------- kitchen ----------

def test_recipe_fallback_is_labelled_and_validated(client):
    d = client.post(f"{V1}/kitchen/recipe", json={"ingredients": ["broccoli"], "diet": "vegan"}).json()["data"]
    assert d["source"] == "local_fallback" and "NOT generated" in d["source_label"] and d["recipes"]
    for bad in ({}, {"ingredients": [], "dish": None}, {"ingredients": ["x"], "diet": "carnivore"}, {"ingredients": ["x"], "servings": 0}):
        assert client.post(f"{V1}/kitchen/recipe", json=bad).status_code == 422


def test_kitchen_chat_scale_and_scan(client):
    r = client.post(f"{V1}/kitchen/chat", json={"messages": [{"role": "user", "content": "chicken temperature?"}]})
    assert r.json()["data"]["source"] == "local_fallback"
    assert client.post(f"{V1}/kitchen/chat", json={"messages": [{"role": "assistant", "content": "hi"}]}).status_code == 422
    rec = client.post(f"{V1}/kitchen/recipe", json={"ingredients": ["chicken"]}).json()["data"]["recipes"][0]
    s = client.post(f"{V1}/kitchen/scale", json={"recipe": rec, "servings": 8}).json()["data"]
    assert s["servings"] == 8
    assert client.post(f"{V1}/kitchen/ingredients/scan", files=[("files", png())]).status_code == 503


def test_provider_timeout_and_http_error_fall_back(make_client):
    httpx = pytest.importorskip("httpx")
    from app.services.llm import HttpLLM
    from tests.helpers import make_settings

    def timeout(request):
        raise httpx.ReadTimeout("slow", request=request)

    def server_error(request):
        return httpx.Response(500, json={"error": "boom sk-secret"})

    for handler, needle in ((timeout, "timed out"), (server_error, "HTTP 500")):
        s = make_settings(llm_provider="anthropic", llm_api_key="sk-secret")
        c = make_client(llm=HttpLLM(s, transport=httpx.MockTransport(handler)))
        d = c.post(f"{V1}/kitchen/recipe", json={"ingredients": ["rice"]}).json()["data"]
        assert d["source"] == "local_fallback" and needle in d["fallback_reason"]
        assert "sk-secret" not in json.dumps(d)


def test_http_llm_success_parsing(make_client):
    httpx = pytest.importorskip("httpx")
    from app.services.llm import HttpLLM
    from tests.helpers import make_settings
    body = {"content": [{"type": "text", "text": "Use medium heat."}]}
    s = make_settings(llm_provider="anthropic", llm_api_key="k")
    c = make_client(llm=HttpLLM(s, transport=httpx.MockTransport(lambda r: httpx.Response(200, json=body))))
    d = c.post(f"{V1}/kitchen/chat", json={"messages": [{"role": "user", "content": "hi"}]}).json()["data"]
    assert d["source"] == "llm" and d["reply"] == "Use medium heat."


# ---------- meal planner ----------

PROFILE = {"age_range": "30-44", "diet": "vegetarian", "allergies": ["dairy", "peanuts"], "avoid_foods": ["mushroom"], "goal": "maintain", "meals_per_day": 4}


def test_profile_validation(client):
    bad_cases = [
        {**PROFILE, "age_range": "toddler"}, {**PROFILE, "meals_per_day": 9}, {**PROFILE, "diet": "carnivore"},
        {**PROFILE, "consent_body_metrics": True},                               # consent without metrics
        {**PROFILE, "weight_kg": 70, "height_cm": 170, "age": 30, "sex": "male"},  # metrics without consent
        {**PROFILE, "consent_body_metrics": True, "sex": "male", "age": 30, "height_cm": 20, "weight_kg": 70},
        {**PROFILE, "age_range": "under_18", "consent_body_metrics": True, "sex": "male", "age": 30, "height_cm": 170, "weight_kg": 70},
        {"diet": "vegan"},
    ]
    for body in bad_cases:
        assert client.post(f"{V1}/meal-planner/profile", json=body).status_code == 422, body
    assert client.post(f"{V1}/meal-planner/profile", json={**PROFILE, "age_range": "under_18", "goal": "lose_weight"}).status_code == 422


def test_meal_plan_flow_with_allergy_exclusions(client):
    assert client.get(f"{V1}/meal-planner").json()["data"] is None                       # empty state
    assert client.post(f"{V1}/meal-planner/generate", json={}).status_code == 404         # no profile yet
    saved = client.post(f"{V1}/meal-planner/profile", json=PROFILE).json()["data"]
    assert set(saved["recognised_allergens"]) == {"milk", "peanut"}
    gen = client.post(f"{V1}/meal-planner/generate", json={"days": 7, "seed": 3}).json()["data"]
    plan = gen["plan"]
    assert len(plan["days"]) == 7 and len(plan["days"][0]["meals"]) == 4 and plan["shopping_list"]
    for d in plan["days"]:
        for m in d["meals"]:
            assert not ({"milk", "peanut"} & set(m["allergens"]))
    # replace + shopping toggle + persistence
    new = client.post(f"{V1}/meal-planner/replace", json={"plan_id": gen["id"], "day": 1, "slot": "dinner"}).json()["data"]["plan"]
    assert not ({"milk", "peanut"} & set(new["days"][0]["meals"][2]["allergens"]))
    key = new["shopping_list"][0]["key"]
    t = client.patch(f"{V1}/meal-planner/shopping", json={"plan_id": gen["id"], "key": key, "purchased": True}).json()["data"]
    assert t["shopping_list"][0]["purchased"] is True
    assert client.get(f"{V1}/meal-planner").json()["data"]["plan"]["shopping_list"][0]["purchased"] is True
    assert client.post(f"{V1}/meal-planner/replace", json={"plan_id": gen["id"], "day": 1, "slot": "dinner", "meal_id": "d-egg-curry"}).status_code in (200, 422)
    assert client.post(f"{V1}/meal-planner/replace", json={"plan_id": "missing", "day": 1, "slot": "dinner"}).status_code == 404


def test_impossible_exclusions_return_clarification_422(client):
    body = {"age_range": "30-44", "diet": "vegan", "allergies": ["soy", "gluten", "peanut", "tree nut", "sesame"],
            "avoid_foods": ["chickpea", "lentil", "potato", "rice", "banana", "carrot", "apple", "oats", "fruit", "kidney", "makhana", "poha", "khichdi", "pasta", "dal"]}
    r = client.post(f"{V1}/meal-planner/generate", json={"profile": body})
    assert r.status_code == 422 and r.json()["error"]["code"] == "clarification_needed"


def test_intake_log_and_dashboard(client):
    assert client.post(f"{V1}/meal-planner/log", json={"name": "Lunch", "kcal": 600, "protein_g": 30}).status_code == 200
    assert client.post(f"{V1}/meal-planner/log", json={"name": "Lunch", "kcal": 600, "date": "2999-01-01"}).status_code == 400
    assert client.post(f"{V1}/meal-planner/log", json={"name": "x", "kcal": -5}).status_code == 422
    s = client.get(f"{V1}/dashboard/summary").json()["data"]
    assert s["today"]["kcal"] == 600 and len(s["weekly"]) == 7


# ---------- history ----------

def test_history_empty_save_filter_delete(client):
    r = client.get(f"{V1}/history")
    assert r.status_code == 200 and r.json()["data"] == [] and r.json()["meta"]["total"] == 0
    s = client.get(f"{V1}/dashboard/summary").json()["data"]
    assert s["recent_analyses"] == [] and s["meal_plan"] is None
    saved = client.post(f"{V1}/history", json={"kind": "food_analysis", "payload": {"food_name": "Pizza"}})
    assert saved.status_code == 201
    rid = saved.json()["data"]["id"]
    assert len(client.get(f"{V1}/history", params={"kind": "food_analysis"}).json()["data"]) == 1
    assert client.get(f"{V1}/history", params={"kind": "bogus"}).status_code == 400
    assert client.post(f"{V1}/history", json={"kind": "profile", "payload": {}}).status_code == 422
    assert client.delete(f"{V1}/history/{rid}").status_code == 200 and client.delete(f"{V1}/history/{rid}").status_code == 404
    assert client.get(f"{V1}/history/{rid}").status_code == 404


def test_hygiene_history_strips_media_previews(client):
    rid = client.post(f"{V1}/history", json={"kind": "hygiene_report", "payload": {"score": {}, "issues": [], "previews": [{"jpeg_b64": "AAAA"}]}}).json()["data"]["id"]
    assert "previews" not in client.get(f"{V1}/history/{rid}").json()["data"]["payload"]
