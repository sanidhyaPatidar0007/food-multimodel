from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.routes.common import ok
from app.deps import Ctx, get_ctx, read_upload, run_in_threadpool
from app.services.freshness import CATEGORIES
from app.utils.errors import AppError
from app.utils.media import validate_image_bytes

router = APIRouter(prefix="/freshness", tags=["freshness"])


@router.get("/categories")
async def categories():
    return ok(CATEGORIES)


@router.post("/analyze", summary="Visual freshness assessment (never a safety guarantee)")
async def analyze(file: UploadFile = File(...), category: str = Form(default="other"), ctx: Ctx = Depends(get_ctx)):
    if category not in CATEGORIES:
        raise AppError(f"Unknown category '{category}'. Choose one of: {', '.join(CATEGORIES)}.")
    data = await read_upload(file, ctx.settings.max_image_bytes)
    img = await run_in_threadpool(validate_image_bytes, data, ctx.settings.max_image_bytes)
    return ok(await ctx.freshness.assess(img, category))
