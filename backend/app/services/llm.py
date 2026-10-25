"""LLM provider abstraction (Anthropic Messages API or OpenAI-compatible chat API).

* Provider chosen by LLM_PROVIDER; key only ever read from the environment.
* Raises ProviderUnavailable when not configured, ProviderError on timeout/HTTP/parse failure.
* Request bodies are built by pure functions so they can be unit-tested without a network.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Protocol

from app.config import PROVIDER_PRESETS, Settings
from app.utils.errors import ProviderError, ProviderUnavailable

log = logging.getLogger("foodverse.llm")


class LLM(Protocol):
    name: str

    @property
    def available(self) -> bool: ...

    # Optional: implementations that cannot read images should expose vision_available = False.
    # Use has_vision(llm) instead of reading the attribute directly.

    async def complete(self, system: str, messages: list[dict], *, images_b64: list[str] | None = None,
                       max_tokens: int = 1500) -> str: ...


def has_vision(llm: Any) -> bool:
    """True when `llm` can accept images. Falls back to `available` for simple stand-ins (tests, custom LLMs)."""
    return bool(getattr(llm, "vision_available", llm.available))


def _content_text(content: Any) -> str:
    """Chat-completion `content` is normally a string, but some providers return null or a list of parts."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return str(content)


def _clean_messages(messages: list[dict]) -> list[dict]:
    """Drop leading assistant turns (Anthropic rejects them; other providers treat them as noise)."""
    msgs = [dict(m) for m in messages]
    while msgs and msgs[0].get("role") != "user":
        msgs.pop(0)
    return msgs


def extract_json(text: str) -> Any:
    """Parse the first JSON object/array in `text` (tolerates ```json fences and prose)."""
    if not isinstance(text, str) or not text.strip():
        raise ProviderError("The AI provider returned an empty response.")
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    for opener, closer in (("{", "}"), ("[", "]")):
        start, end = cleaned.find(opener), cleaned.rfind(closer)
        if start != -1 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                continue
    raise ProviderError("The AI provider returned a response that was not valid JSON.")


def build_anthropic_body(model: str, system: str, messages: list[dict], images_b64: list[str] | None, max_tokens: int) -> dict:
    msgs = _clean_messages(messages)
    if images_b64 and msgs:
        last = msgs[-1]
        blocks = [{"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": b}} for b in images_b64]
        blocks.append({"type": "text", "text": last["content"] if isinstance(last["content"], str) else ""})
        msgs[-1] = {"role": last["role"], "content": blocks}
    return {"model": model, "max_tokens": max_tokens, "system": system, "messages": msgs}


def build_openai_body(model: str, system: str, messages: list[dict], images_b64: list[str] | None, max_tokens: int) -> dict:
    msgs: list[dict] = [{"role": "system", "content": system}] + _clean_messages(messages)
    if images_b64 and len(msgs) > 1:
        last = msgs[-1]
        parts = [{"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b}"}} for b in images_b64]
        parts.append({"type": "text", "text": last["content"]})
        msgs[-1] = {"role": last["role"], "content": parts}
    return {"model": model, "max_tokens": max_tokens, "messages": msgs}


class HttpLLM:
    def __init__(self, settings: Settings, transport: Any = None):
        self.s = settings
        self.name = settings.llm_provider
        self._transport = transport  # injectable httpx transport for tests

    @property
    def available(self) -> bool:
        prov = self.s.llm_provider
        if prov == "anthropic":
            return bool(self.s.llm_api_key and self.s.llm_model)
        preset = PROVIDER_PRESETS.get(prov)
        if not preset or not self.s.llm_model:
            return False  # unknown provider, or a preset (groq/openrouter) with no LLM_MODEL chosen
        return bool(self.s.llm_api_key) or not preset["needs_key"]  # local Ollama needs no key

    @property
    def vision_available(self) -> bool:
        """Image features need a vision-capable model: LLM_VISION_MODEL, or the main model for providers that default to vision."""
        return self.available and bool(self.s.llm_vision_model)

    async def complete(self, system: str, messages: list[dict], *, images_b64: list[str] | None = None,
                       max_tokens: int = 1500) -> str:
        if not self.available:
            raise ProviderUnavailable("No LLM provider is configured. Set LLM_PROVIDER (and LLM_API_KEY / LLM_MODEL where needed) in backend/.env.")
        if images_b64 and not self.vision_available:
            raise ProviderUnavailable("The configured AI model cannot read images. Set LLM_VISION_MODEL to a vision-capable model in backend/.env.")
        model = self.s.llm_vision_model if images_b64 else self.s.llm_model
        import httpx  # lazy: keeps domain code importable without httpx

        if self.s.llm_provider == "anthropic":
            url = (self.s.llm_base_url or "https://api.anthropic.com").rstrip("/") + "/v1/messages"
            headers = {"x-api-key": self.s.llm_api_key, "anthropic-version": "2023-06-01", "content-type": "application/json"}
            body = build_anthropic_body(model, system, messages, images_b64, max_tokens)
        else:
            root = (self.s.llm_base_url or PROVIDER_PRESETS.get(self.s.llm_provider, {}).get("base_url", "https://api.openai.com/v1")).rstrip("/")
            url = root if root.endswith("/chat/completions") else root + "/chat/completions"
            headers = {"content-type": "application/json"}
            if self.s.llm_api_key:
                headers["authorization"] = f"Bearer {self.s.llm_api_key}"
            body = build_openai_body(model, system, messages, images_b64, max_tokens)
        try:
            async with httpx.AsyncClient(timeout=self.s.llm_timeout_seconds, transport=self._transport) as client:
                resp = await client.post(url, headers=headers, json=body)
        except httpx.TimeoutException as exc:
            log.warning("LLM timeout after %ss", self.s.llm_timeout_seconds)
            raise ProviderError("The AI provider timed out. Please try again.") from exc
        except httpx.HTTPError as exc:
            log.warning("LLM transport error: %s", type(exc).__name__)
            raise ProviderError("Could not reach the AI provider.") from exc
        if resp.status_code >= 400:
            log.warning("LLM HTTP %s", resp.status_code)  # body intentionally not logged
            raise ProviderError(f"The AI provider returned an error (HTTP {resp.status_code}).")
        try:
            data = resp.json()
            if self.s.llm_provider == "anthropic":
                text = "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")
                truncated = data.get("stop_reason") == "max_tokens"
            else:
                choice = data["choices"][0]
                text = _content_text(choice["message"].get("content"))
                truncated = choice.get("finish_reason") == "length"
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as exc:
            raise ProviderError("The AI provider returned an unexpected response format.") from exc
        if not text.strip():
            # Reasoning models can spend the whole token budget thinking and return nothing.
            raise ProviderError("The AI model ran out of output tokens before answering. Try again or use a non-reasoning model."
                                if truncated else "The AI provider returned an empty response.")
        return text


def build_llm(settings: Settings, transport: Any = None) -> HttpLLM:
    return HttpLLM(settings, transport)
