"""Regression tests for deployment-hardening fixes."""
import asyncio
import json
from datetime import date, timedelta

import pytest

from app.config import Settings
from app.services.llm import HttpLLM, extract_json, has_vision
from app.utils.errors import ProviderError, ProviderUnavailable
from app.utils.ratelimit import RateLimiter
from tests.helpers import FakeLLM, make_image_bytes, make_settings

V1 = "/api/v1"
httpx = pytest.importorskip("httpx")


def _llm(handler, **kw):
    s = make_settings(llm_provider="groq", llm_api_key="k", llm_model="text-model", **kw)
    return HttpLLM(s, transport=httpx.MockTransport(handler))


def _ok(content, finish="stop"):
    return lambda r: httpx.Response(200, json={"choices": [{"message": {"content": content}, "finish_reason": finish}]})


# ---------- LLM client ----------
def test_null_empty_and_truncated_content_become_provider_errors():
    for content, finish, needle in ((None, "stop", "empty"), ("", "stop", "empty"), (None, "length", "ran out")):
        with pytest.raises(ProviderError, match=needle):
            asyncio.run(_llm(_ok(content, finish)).complete("s", [{"role": "user", "content": "x"}]))


def test_list_content_parts_are_joined():
    out = asyncio.run(_llm(_ok([{"type": "text", "text": "he"}, {"type": "text", "text": "llo"}])).complete("s", [{"role": "user", "content": "x"}]))
    assert out == "hello"


def test_extract_json_rejects_empty():
    with pytest.raises(ProviderError):
        extract_json("   ")


def test_text_only_model_never_receives_images():
    llm = _llm(_ok("x"))
    assert llm.available and not llm.vision_available and not has_vision(llm)
    with pytest.raises(ProviderUnavailable, match="LLM_VISION_MODEL"):
        asyncio.run(llm.complete("s", [{"role": "user", "content": "x"}], images_b64=["AAAA"]))


def test_vision_model_is_used_only_for_image_calls():
    seen = []

    def handler(req):
        seen.append(json.loads(req.content)["model"])
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    llm = _llm(handler, llm_vision_model="vision-model")
    msg = [{"role": "user", "content": "x"}]
    asyncio.run(llm.complete("s", msg))
    asyncio.run(llm.complete("s", msg, images_b64=["AAAA"]))
    assert seen == ["text-model", "vision-model"]


def test_leading_assistant_messages_are_dropped():
    bodies = []

    def handler(req):
        bodies.append(json.loads(req.content))
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    asyncio.run(_llm(handler).complete("s", [{"role": "assistant", "content": "hi"}, {"role": "user", "content": "q"}]))
    assert [m["role"] for m in bodies[0]["messages"]] == ["system", "user"]


def test_vision_defaults_per_provider(monkeypatch):
    monkeypatch.setenv("FOODVERSE_SKIP_DOTENV", "1")
    for k in ("LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL", "LLM_VISION_MODEL"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "gemini")
    assert Settings.from_env().llm_vision_model == "gemini-2.5-flash"
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("LLM_MODEL", "openai/gpt-oss-20b")
    assert Settings.from_env().llm_vision_model == ""          # text-only by default => photo features off
    monkeypatch.setenv("LLM_VISION_MODEL", "some-vision-model")
    assert Settings.from_env().llm_vision_model == "some-vision-model"


def test_cors_origin_trailing_slash_is_normalised(monkeypatch):
    monkeypatch.setenv("FOODVERSE_SKIP_DOTENV", "1")
    monkeypatch.setenv("CORS_ORIGINS", "https://a.example.com/, https://b.example.com")
    assert Settings.from_env().cors_origins == ["https://a.example.com", "https://b.example.com"]


# ---------- API ----------
def test_text_only_llm_degrades_cleanly_for_photo_features(make_client):
    llm = _llm(_ok("{}"))
    c = make_client(llm=llm)
    health = c.get(f"{V1}/health").json()["data"]["providers"]
    assert health["llm"]["configured"] and not health["llm_vision"]["configured"] and not health["hygiene_detector"]["configured"]
    r = c.post(f"{V1}/kitchen/ingredients/scan", files=[("files", ("a.png", make_image_bytes(), "image/png"))])
    assert r.status_code == 503 and r.json()["error"]["code"] == "provider_unavailable"
    d = c.post(f"{V1}/food/analyze", files={"file": ("a.png", make_image_bytes(), "image/png")}).json()["data"]
    assert d["recognition"]["status"] == "unavailable"          # no bogus HTTP-400 "recognition failed"


def test_kitchen_survives_odd_llm_json(make_client):
    for reply in ('[{"title":"x"}]', "[1,2]", '"just a string"', '{"recipes":[1]}', '{"recipes":null}'):
        c = make_client(llm=FakeLLM(reply))
        r = c.post(f"{V1}/kitchen/recipe", json={"ingredients": ["rice"]})
        assert r.status_code == 200 and r.json()["data"]["source"] == "local_fallback", reply


def test_scale_rejects_malformed_recipe(client):
    for recipe in ({"ingredients": [1, 2], "servings": 2}, {"ingredients": [], "servings": 0}, {"ingredients": [], "servings": True}):
        assert client.post(f"{V1}/kitchen/scale", json={"recipe": recipe, "servings": 3}).status_code == 422


def test_hygiene_frames_accepts_the_ui_maximum(client):
    r = client.post(f"{V1}/hygiene/frames", files=[("files", ("a.png", make_image_bytes(), "image/png"))],
                    data={"interval_seconds": "2", "max_frames": "120"})
    assert r.status_code == 200


def test_intake_date_tolerates_client_timezone_ahead_of_server(client):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    assert client.post(f"{V1}/meal-planner/log", json={"name": "x", "kcal": 100, "date": tomorrow}).status_code == 200
    far = (date.today() + timedelta(days=3)).isoformat()
    assert client.post(f"{V1}/meal-planner/log", json={"name": "x", "kcal": 100, "date": far}).status_code == 400


def test_dashboard_uses_client_today(client):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    client.post(f"{V1}/meal-planner/log", json={"name": "x", "kcal": 321, "date": tomorrow})
    d = client.get(f"{V1}/dashboard/summary", params={"today": tomorrow}).json()["data"]
    assert d["today"]["date"] == tomorrow and d["today"]["kcal"] == 321 and d["weekly"][-1]["date"] == tomorrow
    assert client.get(f"{V1}/dashboard/summary", params={"today": "2001-01-01"}).status_code == 400


def test_rate_limit_returns_envelope_with_cors_headers(make_client):
    c = make_client(rate_limit_per_minute=3, cors_origins=["http://localhost:5173"])
    h = {"Origin": "http://localhost:5173"}
    codes = [c.get(f"{V1}/food/reference", headers=h).status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]
    r = c.get(f"{V1}/food/reference", headers=h)
    assert r.json()["error"]["code"] == "rate_limited" and int(r.headers["Retry-After"]) >= 1
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"   # browser can read the 429
    assert c.get(f"{V1}/health").status_code == 200 and c.get("/healthz").json() == {"status": "ok"}  # probes exempt


def test_ai_endpoints_have_their_own_stricter_limit(make_client):
    c = make_client(rate_limit_ai_per_minute=2)
    codes = [c.post(f"{V1}/kitchen/chat", json={"messages": [{"role": "user", "content": "hi"}]}).status_code for _ in range(4)]
    assert codes == [200, 200, 429, 429]
    assert c.get(f"{V1}/food/reference").status_code == 200


def test_oversized_request_rejected_before_parsing(make_client):
    c = make_client(max_image_mb=0.01, max_video_mb=0.01)
    r = c.post(f"{V1}/food/analyze", content=b"x" * (2 * 1024 * 1024), headers={"content-type": "multipart/form-data; boundary=x"})
    assert r.status_code == 413 and r.json()["error"]["code"] == "payload_too_large"


def test_docs_disabled_in_production_and_security_headers(make_client):
    c = make_client(app_env="production", enable_docs=False)
    assert c.get("/docs").status_code == 404 and c.get("/openapi.json").status_code == 404
    r = c.get(f"{V1}/health")
    assert r.headers["x-frame-options"] == "DENY" and r.headers["x-content-type-options"] == "nosniff"
    assert make_client().get("/docs").status_code == 200


def test_rate_limiter_unit():
    rl = RateLimiter(window_seconds=10)
    assert [rl.check("a", 2, now=t)[0] for t in (0, 1, 2)] == [True, True, False]
    assert rl.check("a", 2, now=11)[0] is True            # window slid
    assert rl.check("b", 0)[0] is True                    # disabled
    assert rl.check("c", 1, now=0)[0] and rl.check("c", 1, now=1)[1] >= 1


def test_production_warnings_never_leak_secrets():
    s = make_settings(app_env="production", llm_provider="groq", llm_api_key="sk-secret", llm_model="m")
    text = " ".join(s.warnings())
    assert "CORS_ORIGINS" in text and "vision" in text.lower() and "sk-secret" not in text


def test_sqlite_file_uses_wal(tmp_path):
    from app.database.repository import Repository
    r = Repository(str(tmp_path / "db" / "x.db"))
    assert r._conn.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
    r.add("saved_recipe", {"title": "t"})
    assert r.count() == 1
    r.close()


# ---------- freshness: LLM vision + cautious heuristic ----------
def _fresh_svc(reply=None, error=None, vision=True):
    from app.services.freshness import FreshnessService
    llm = FakeLLM(reply or "", error=error, available=vision)
    return FreshnessService(make_settings(), llm=llm)


def _img():
    from PIL import Image
    import numpy as np
    arr = np.random.default_rng(3).normal(130, 50, (400, 400, 3)).clip(0, 255).astype("uint8")
    return Image.fromarray(arr)


def _run(svc, cat, img=None):
    return asyncio.run(svc.assess(img or _img(), cat))


def _reply(verdict, concern="none", problem=""):
    return json.dumps({"verdict": verdict, "image_problem": problem,
                       "observations": [{"item": "apple", "finding": "x", "concern": concern}]})


def test_llm_freshness_is_used_and_labelled():
    r = _run(_fresh_svc(_reply("no_visible_deterioration")), "fruit")
    assert r["verdict"] == "no_visible_deterioration" and r["model"]["kind"] == "llm_vision" and r["confidence"] is None
    assert "not a validated" in r["model"]["label"] and r["mode"] == "trained_model"


def test_llm_freshness_safety_clamps():
    # high-risk categories never get a positive verdict, whatever the model says
    for cat in ("meat", "fish", "dairy", "cooked_meal"):
        assert _run(_fresh_svc(_reply("no_visible_deterioration")), cat)["verdict"] == "uncertain"
    # deterioration needs a specific observed sign
    assert _run(_fresh_svc(_reply("signs_of_deterioration", "none")), "fruit")["verdict"] == "uncertain"
    assert _run(_fresh_svc(_reply("signs_of_deterioration", "strong")), "fruit")["verdict"] == "signs_of_deterioration"
    # image problem reported by the model blocks a positive verdict
    assert _run(_fresh_svc(_reply("no_visible_deterioration", problem="blurry")), "fruit")["verdict"] == "uncertain"
    # garbage verdict -> uncertain
    assert _run(_fresh_svc(_reply("totally safe!")), "fruit")["verdict"] == "uncertain"


def test_llm_freshness_failure_falls_back_with_explanation():
    for svc in (_fresh_svc(error=ProviderError("boom")), _fresh_svc("not json"), _fresh_svc("[1]")):
        r = _run(svc, "fruit")
        assert r["model"]["kind"] == "heuristic_baseline" and any("AI vision check failed" in x for x in r["reasons"])


def test_text_only_llm_uses_baseline_without_calling_it():
    from app.services.freshness import FreshnessService
    llm = _llm(_ok("{}"))   # groq text-only model: available but no vision
    r = asyncio.run(FreshnessService(make_settings(), llm=llm).assess(_img(), "fruit"))
    assert r["model"]["kind"] == "heuristic_baseline"


def test_baseline_never_calls_cooked_or_unknown_food_deteriorated():
    from PIL import Image, ImageDraw
    import numpy as np
    im = Image.new("RGB", (400, 400), (60, 40, 30))          # dark brown table, like the reported false positive
    ImageDraw.Draw(im).ellipse((60, 60, 340, 340), fill=(25, 15, 10))
    arr = np.array(im).astype(int) + np.random.default_rng(1).normal(0, 14, (400, 400, 3))
    im = Image.fromarray(arr.clip(0, 255).astype("uint8"))
    svc = _fresh_svc(vision=False)
    for cat in ("cooked_meal", "other"):
        assert _run(svc, cat, im)["verdict"] != "signs_of_deterioration"
