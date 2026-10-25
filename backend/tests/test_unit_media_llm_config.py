import asyncio

import pytest

from app.config import Settings
from app.services import llm as L
from app.services.llm import HttpLLM, build_anthropic_body, build_openai_body, extract_json
from app.utils.errors import MediaError, PayloadTooLarge, ProviderError, ProviderUnavailable, UnsupportedMediaType
from app.utils.media import sniff_video, validate_image_bytes, validate_video_bytes

from tests.helpers import make_image_bytes, make_video_bytes

LIMIT = 8 * 1024 * 1024


def test_valid_images_in_all_supported_formats():
    for fmt in ("JPEG", "PNG", "WEBP"):
        img = validate_image_bytes(make_image_bytes(fmt), LIMIT)
        assert img.mode == "RGB" and img.size == (320, 320)


def test_empty_upload_rejected():
    with pytest.raises(MediaError):
        validate_image_bytes(b"", LIMIT)


def test_unsupported_type_rejected_even_if_decodable():
    gif = make_image_bytes("GIF")
    with pytest.raises(UnsupportedMediaType):
        validate_image_bytes(gif, LIMIT)
    with pytest.raises(UnsupportedMediaType):
        validate_image_bytes(b"%PDF-1.4 not an image", LIMIT)


def test_corrupted_image_rejected():
    good = make_image_bytes("PNG")
    with pytest.raises(MediaError):
        validate_image_bytes(good[:60] + b"garbage" * 5, LIMIT)


def test_oversize_and_tiny_images_rejected():
    with pytest.raises(PayloadTooLarge):
        validate_image_bytes(make_image_bytes("PNG"), 100)
    with pytest.raises(MediaError):
        validate_image_bytes(make_image_bytes("PNG", size=(16, 16), circle=False), LIMIT)


def test_video_validation():
    vid = make_video_bytes(seconds=1)
    assert validate_video_bytes(vid, 50 * 1024 * 1024) == "video/x-msvideo"
    with pytest.raises(UnsupportedMediaType):
        validate_video_bytes(b"this is plain text, not a video", 1000)
    with pytest.raises(PayloadTooLarge):
        validate_video_bytes(vid, 10)
    assert sniff_video(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 8) == "video/mp4"


def test_extract_json_variants():
    assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert extract_json('Sure! Here you go: {"a": [1,2]} hope it helps') == {"a": [1, 2]}
    with pytest.raises(ProviderError):
        extract_json("no json at all")


def test_request_body_builders():
    a = build_anthropic_body("m", "sys", [{"role": "user", "content": "hi"}], ["AAA"], 100)
    assert a["system"] == "sys" and a["messages"][0]["content"][0]["type"] == "image"
    o = build_openai_body("m", "sys", [{"role": "user", "content": "hi"}], ["AAA"], 100)
    assert o["messages"][0]["role"] == "system" and o["messages"][1]["content"][0]["type"] == "image_url"


def test_missing_api_key_means_unavailable_not_crash():
    for provider in ("none", "anthropic", "openai"):
        s = Settings(llm_provider=provider, llm_api_key="")
        client = HttpLLM(s)
        assert client.available is False
        with pytest.raises(ProviderUnavailable):
            asyncio.run(client.complete("s", [{"role": "user", "content": "x"}]))


def test_configured_flag_requires_both_provider_and_key():
    assert HttpLLM(Settings(llm_provider="anthropic", llm_api_key="k")).available
    assert not HttpLLM(Settings(llm_provider="none", llm_api_key="k")).available


def test_settings_defaults_do_not_contain_secrets():
    s = Settings()
    assert s.llm_api_key == "" and s.max_image_bytes == 8 * 1024 * 1024


def test_free_provider_presets_resolve_endpoint_and_model(monkeypatch=None):
    import os
    saved = {k: os.environ.get(k) for k in ("LLM_PROVIDER", "LLM_API_KEY", "LLM_MODEL", "LLM_BASE_URL")}
    try:
        for k in saved: os.environ.pop(k, None)
        os.environ.update({"LLM_PROVIDER": "gemini", "LLM_API_KEY": "k"})
        s = Settings.from_env()
        assert s.llm_base_url == "https://generativelanguage.googleapis.com/v1beta/openai" and s.llm_model == "gemini-2.5-flash"
        assert HttpLLM(s).available
        os.environ["LLM_PROVIDER"] = "groq"                       # no default model => unavailable until LLM_MODEL is chosen
        s = Settings.from_env()
        assert s.llm_model == "" and not HttpLLM(s).available
        os.environ["LLM_MODEL"] = "some-model"
        assert HttpLLM(Settings.from_env()).available
        os.environ.pop("LLM_API_KEY"); os.environ["LLM_PROVIDER"] = "ollama"; os.environ.pop("LLM_MODEL")
        s = Settings.from_env()
        assert s.llm_base_url.startswith("http://localhost:11434") and HttpLLM(s).available   # local: no key needed
        os.environ["LLM_PROVIDER"] = "mystery"
        assert not HttpLLM(Settings.from_env()).available
    finally:
        for k, v in saved.items():
            os.environ.pop(k, None)
            if v is not None: os.environ[k] = v


def test_openai_compatible_url_and_optional_auth_header():
    httpx = pytest.importorskip("httpx")
    seen = {}
    def handler(req):
        seen["url"], seen["auth"] = str(req.url), req.headers.get("authorization")
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}]})
    for provider, key, url, auth in (("gemini", "K", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "Bearer K"),
                                     ("ollama", "", "http://localhost:11434/v1/chat/completions", None)):
        from app.config import PROVIDER_PRESETS
        s = Settings(llm_provider=provider, llm_api_key=key, llm_model="m", llm_base_url=PROVIDER_PRESETS[provider]["base_url"])
        out = asyncio.run(HttpLLM(s, transport=httpx.MockTransport(handler)).complete("s", [{"role": "user", "content": "x"}]))
        assert out == "hi" and seen["url"] == url and seen["auth"] == auth


def test_classifier_normalisation_is_configurable():
    import numpy as np
    from PIL import Image
    from app.utils.imaging import preprocess_for_classifier
    white = Image.new("RGB", (64, 64), (255, 255, 255))
    assert np.allclose(preprocess_for_classifier(white, 32, (0.5,) * 3, (0.5,) * 3), 1.0)        # (1-0.5)/0.5
    assert preprocess_for_classifier(white, 32).max() > 2.0                                       # ImageNet default
    assert preprocess_for_classifier(white, 32).shape == (1, 3, 32, 32)
