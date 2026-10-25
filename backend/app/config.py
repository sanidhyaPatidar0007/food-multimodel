"""Application settings. Framework-free so domain code and tests can import it."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
_dotenv_loaded = False


def _load_dotenv() -> None:
    """Minimal .env loader. Never overrides variables already set in the real environment.

    Looks in the backend directory first (so it works regardless of the working directory), then the
    current directory. Runs once per process; set FOODVERSE_SKIP_DOTENV=1 to disable (tests, containers
    that inject configuration through the environment).
    """
    global _dotenv_loaded
    if _dotenv_loaded or os.environ.get("FOODVERSE_SKIP_DOTENV"):
        return
    _dotenv_loaded = True
    for path in (BACKEND_DIR / ".env", Path(".env")):
        if not path.is_file():
            continue
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            value = value.split(" #", 1)[0].strip().strip('"').strip("'")
            os.environ.setdefault(key.strip(), value)


def _f(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return float(default)


def _b(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _i(name: str, default: int) -> int:
    try:
        return int(float(os.environ.get(name, default)))
    except ValueError:
        return int(default)


# OpenAI-compatible provider presets (root URL; "/chat/completions" is appended). Free tiers change -
# check each provider's current limits. Models with no default MUST be set via LLM_MODEL.
PROVIDER_PRESETS = {
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "gemini-2.5-flash", "needs_key": True},
    "groq": {"base_url": "https://api.groq.com/openai/v1", "model": "", "needs_key": True},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "model": "", "needs_key": True},
    "ollama": {"base_url": "http://localhost:11434/v1", "model": "llama3.2-vision", "needs_key": False},
    "openai": {"base_url": "https://api.openai.com/v1", "model": "", "needs_key": True},
}
SUPPORTED_PROVIDERS = {"anthropic", *PROVIDER_PRESETS}
# Providers whose main model is assumed to accept images. For anything else (groq, openrouter, custom
# base URLs) image features stay OFF until LLM_VISION_MODEL names a vision-capable model explicitly.
VISION_BY_DEFAULT = {"anthropic", "gemini", "ollama", "openai"}


def _triple(name: str, default: tuple[float, float, float]) -> tuple[float, float, float]:
    raw = os.environ.get(name, "")
    try:
        vals = tuple(float(x) for x in raw.split(",")) if raw else default
        return vals if len(vals) == 3 else default  # type: ignore[return-value]
    except ValueError:
        return default


IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)


@dataclass
class Settings:
    app_env: str = "development"
    log_level: str = "INFO"
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:5173"])
    database_path: str = "./data/foodverse.db"
    max_image_mb: float = 8
    max_video_mb: float = 60
    max_video_seconds: float = 120
    llm_provider: str = "none"
    llm_api_key: str = ""
    llm_model: str = "claude-sonnet-5-5"
    llm_base_url: str = ""
    llm_timeout_seconds: float = 45
    llm_vision_model: str = ""
    enable_docs: bool = True
    rate_limit_per_minute: int = 120
    rate_limit_ai_per_minute: int = 20
    vision_provider: str = "auto"
    food_model_path: str = "./models_weights/food_classifier.onnx"
    food_labels_path: str = "./models_weights/food_labels.txt"
    food_model_input_size: int = 224
    food_model_mean: tuple = IMAGENET_MEAN
    food_model_std: tuple = IMAGENET_STD
    freshness_model_mean: tuple = IMAGENET_MEAN
    freshness_model_std: tuple = IMAGENET_STD
    freshness_model_path: str = "./models_weights/freshness_classifier.onnx"
    freshness_labels_path: str = "./models_weights/freshness_labels.txt"
    hygiene_frame_interval_seconds: float = 2.0
    hygiene_max_frames: int = 24

    @property
    def max_image_bytes(self) -> int:
        return int(self.max_image_mb * 1024 * 1024)

    @property
    def max_video_bytes(self) -> int:
        return int(self.max_video_mb * 1024 * 1024)

    @property
    def is_production(self) -> bool:
        return self.app_env.lower() == "production"

    def warnings(self) -> list[str]:
        """Configuration problems worth logging at startup (never raises, never includes secrets)."""
        out: list[str] = []
        if self.is_production:
            if all("localhost" in o or "127.0.0.1" in o for o in self.cors_origins):
                out.append("CORS_ORIGINS only lists localhost; browsers on your real domain will be blocked unless the "
                           "frontend is served from the same origin (e.g. through the bundled nginx proxy).")
            if self.database_path == ":memory:":
                out.append("DATABASE_PATH is :memory:, so saved data is lost on restart.")
            if self.rate_limit_per_minute <= 0 or self.rate_limit_ai_per_minute <= 0:
                out.append("Rate limiting is disabled; anyone who can reach the API can spend your AI provider quota.")
        if self.llm_provider not in ("none", "") and self.llm_provider not in SUPPORTED_PROVIDERS:
            out.append(f"LLM_PROVIDER '{self.llm_provider}' is not supported; the LLM is disabled.")
        if self.llm_provider in PROVIDER_PRESETS and not self.llm_model:
            out.append(f"LLM_PROVIDER={self.llm_provider} needs LLM_MODEL; the LLM is disabled until it is set.")
        if self.llm_provider not in ("none", "") and self.llm_model and not self.llm_vision_model:
            out.append("No vision model configured: photo features (ingredient photos, LLM food recognition, hygiene "
                       "detector) stay off. Set LLM_VISION_MODEL to a vision-capable model to enable them.")
        return out

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv()
        provider = os.environ.get("LLM_PROVIDER", "none").lower()
        preset = PROVIDER_PRESETS.get(provider, {})
        default_model = "claude-sonnet-5-5" if provider == "anthropic" else preset.get("model", "")
        # Browsers send Origin without a trailing slash, so "https://app.example.com/" would never match.
        origins = [o.strip().rstrip("/") for o in os.environ.get("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()]
        app_env = os.environ.get("APP_ENV", "development")
        model = os.environ.get("LLM_MODEL") or default_model
        vision_model = os.environ.get("LLM_VISION_MODEL") or (model if provider in VISION_BY_DEFAULT else "")
        return cls(
            app_env=app_env,
            log_level=os.environ.get("LOG_LEVEL", "INFO").upper(),
            cors_origins=origins,
            database_path=os.environ.get("DATABASE_PATH", "./data/foodverse.db"),
            max_image_mb=_f("MAX_IMAGE_MB", 8),
            max_video_mb=_f("MAX_VIDEO_MB", 60),
            max_video_seconds=_f("MAX_VIDEO_SECONDS", 120),
            llm_provider=provider,
            llm_api_key=os.environ.get("LLM_API_KEY", ""),
            llm_model=model,
            llm_vision_model=vision_model,
            llm_base_url=os.environ.get("LLM_BASE_URL") or preset.get("base_url", ""),
            llm_timeout_seconds=_f("LLM_TIMEOUT_SECONDS", 45),
            enable_docs=_b("ENABLE_DOCS", app_env.lower() != "production"),
            rate_limit_per_minute=_i("RATE_LIMIT_PER_MINUTE", 120),
            rate_limit_ai_per_minute=_i("RATE_LIMIT_AI_PER_MINUTE", 20),
            vision_provider=os.environ.get("VISION_PROVIDER", "auto").lower(),
            food_model_path=os.environ.get("FOOD_MODEL_PATH", "./models_weights/food_classifier.onnx"),
            food_labels_path=os.environ.get("FOOD_LABELS_PATH", "./models_weights/food_labels.txt"),
            food_model_input_size=_i("FOOD_MODEL_INPUT_SIZE", 224),
            food_model_mean=_triple("FOOD_MODEL_MEAN", IMAGENET_MEAN), food_model_std=_triple("FOOD_MODEL_STD", IMAGENET_STD),
            freshness_model_mean=_triple("FRESHNESS_MODEL_MEAN", IMAGENET_MEAN), freshness_model_std=_triple("FRESHNESS_MODEL_STD", IMAGENET_STD),
            freshness_model_path=os.environ.get("FRESHNESS_MODEL_PATH", "./models_weights/freshness_classifier.onnx"),
            freshness_labels_path=os.environ.get("FRESHNESS_LABELS_PATH", "./models_weights/freshness_labels.txt"),
            hygiene_frame_interval_seconds=_f("HYGIENE_FRAME_INTERVAL_SECONDS", 2.0),
            hygiene_max_frames=_i("HYGIENE_MAX_FRAMES", 24),
        )


@lru_cache
def get_settings() -> Settings:
    return Settings.from_env()
