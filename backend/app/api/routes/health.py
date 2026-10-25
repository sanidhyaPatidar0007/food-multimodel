from fastapi import APIRouter, Depends

from app import __version__
from app.api.routes.common import ok
from app.deps import Ctx, get_ctx
from app.services.llm import has_vision

router = APIRouter(tags=["health"])


@router.head("/health", include_in_schema=False)
@router.get("/health", summary="Service health and provider configuration (no secrets)")
async def health(ctx: Ctx = Depends(get_ctx)):
    s = ctx.settings
    db_ok = ctx.repo.ping()
    providers = {
        "llm": {"configured": ctx.llm.available, "detail": f"{s.llm_provider}:{s.llm_model}" if ctx.llm.available else "not configured - local fallback recipes are used"},
        "llm_vision": {"configured": has_vision(ctx.llm), "detail": s.llm_vision_model if has_vision(ctx.llm) else "no vision model - set LLM_VISION_MODEL to enable photo features with the LLM"},
        "food_recognition": {"configured": ctx.food.provider() != "none", "detail": ctx.food.provider() if ctx.food.provider() != "none" else "no model or key - manual food selection only"},
        "freshness_model": {"configured": ctx.freshness.mode != "baseline_demo", "detail": ctx.freshness.mode},
        "hygiene_detector": {"configured": ctx.hygiene_detector.name != "none", "detail": ctx.hygiene_detector.name},
    }
    return ok({"status": "ok" if db_ok else "degraded", "version": __version__, "environment": s.app_env, "database": db_ok,
               "providers": providers, "limits": {"max_image_mb": s.max_image_mb, "max_video_mb": s.max_video_mb, "max_video_seconds": s.max_video_seconds}})
