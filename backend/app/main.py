"""FastAPI application factory."""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import __version__
from app.api.routes import food, freshness, health, history, hygiene, kitchen, meal_planner
from app.config import Settings, get_settings
from app.database.repository import create_repository
from app.deps import build_ctx
from app.services.llm import build_llm
from app.utils.errors import AppError
from app.utils.ratelimit import RateLimiter

log = logging.getLogger("foodverse")

# Endpoints that call an AI provider or do heavy image/video work get the stricter per-IP limit.
_AI_PREFIXES = ("/api/v1/food/analyze", "/api/v1/freshness/analyze", "/api/v1/hygiene/", "/api/v1/kitchen/recipe",
                "/api/v1/kitchen/chat", "/api/v1/kitchen/ingredients")


def _error(status: int, code: str, message: str, request: Request, details: dict | None = None) -> JSONResponse:
    rid = getattr(request.state, "request_id", None)
    resp = JSONResponse({"ok": False, "error": {"code": code, "message": message, "details": details or {}, "request_id": rid}}, status_code=status)
    return resp


def create_app(settings: Settings | None = None, llm=None, repo=None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO),
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        _repo = repo or create_repository(settings.database_path)
        _llm = llm or build_llm(settings)
        app.state.ctx = build_ctx(settings, _repo, _llm)
        for w in settings.warnings():
            log.warning("config: %s", w)
        log.info("FoodVerse AI %s started (env=%s, llm=%s, food_provider=%s)", __version__, settings.app_env,
                 _llm.available, app.state.ctx.food.provider())
        yield
        if repo is None:
            _repo.close()

    docs = {} if settings.enable_docs else {"docs_url": None, "redoc_url": None, "openapi_url": None}
    app = FastAPI(title="FoodVerse AI API", version=__version__, lifespan=lifespan, **docs,
                  description="Multimodal food intelligence API. Results are estimates / preliminary assessments, not medical or regulatory advice.")
    limiter = RateLimiter()
    # Reject oversized bodies before they are parsed/spooled. Multipart overhead gets a little headroom.
    max_body = max(settings.max_video_bytes, settings.max_image_bytes * 24) + 1024 * 1024

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = uuid.uuid4().hex[:12]
        start = time.perf_counter()
        path = request.url.path
        if request.method == "OPTIONS" or path in ("/healthz", "/api/v1/health"):
            pass
        else:
            declared = request.headers.get("content-length", "")
            if declared.isdigit() and int(declared) > max_body:
                return _error(413, "payload_too_large", f"The upload is larger than the {max_body // (1024 * 1024)} MB request limit.", request)
            ip = request.client.host if request.client else "unknown"
            ai = request.method == "POST" and path.startswith(_AI_PREFIXES)
            allowed, retry = limiter.check(f"{'ai' if ai else 'gen'}:{ip}",
                                           settings.rate_limit_ai_per_minute if ai else settings.rate_limit_per_minute)
            if not allowed:
                resp = _error(429, "rate_limited", f"Too many requests. Please wait {retry} seconds and try again.", request)
                resp.headers["Retry-After"] = str(retry)
                return resp
        try:
            response = await call_next(request)
        except Exception:  # last-resort guard; handler below formats normal errors
            log.exception("Unhandled error rid=%s %s %s", request.state.request_id, request.method, request.url.path)
            return _error(500, "internal_error", "An unexpected error occurred.", request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        log.info("rid=%s %s %s -> %s %.0fms", request.state.request_id, request.method, request.url.path,
                 response.status_code, (time.perf_counter() - start) * 1000)
        return response

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        return _error(exc.status_code, exc.code, exc.message, request, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        problems = [{"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]} for e in exc.errors()]
        return _error(422, "validation_error", "The request was invalid. " + "; ".join(f"{p['field']}: {p['message']}" for p in problems[:3]), request, {"problems": problems})

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        return _error(exc.status_code, "http_error", str(exc.detail), request)

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        log.exception("Unhandled error rid=%s", getattr(request.state, "request_id", "-"))
        return _error(500, "internal_error", "An unexpected error occurred.", request)

    # Added last => outermost, so CORS headers are also present on 413/429 responses produced by the middleware above.
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"], allow_headers=["*"],
                       expose_headers=["X-Request-ID", "Retry-After"])

    @app.head("/healthz", include_in_schema=False)
    @app.get("/healthz", include_in_schema=False)
    async def liveness():
        """Cheap liveness probe for load balancers / containers (no database or provider calls)."""
        return {"status": "ok"}

    for module in (health, food, freshness, hygiene, kitchen, meal_planner, history):
        app.include_router(module.router, prefix="/api/v1")
    return app


app = create_app()
