from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.routes.common import ok
from app.api.schemas import FoodManualRequest
from app.deps import Ctx, get_ctx, read_upload, run_in_threadpool
from app.services import nutrition
from app.utils.media import validate_image_bytes

router = APIRouter(prefix="/food", tags=["food"])


@router.post("/analyze", summary="Recognise food in an image and estimate nutrition")
async def analyze(file: UploadFile = File(...), grams: float | None = Form(default=None, ge=1, le=3000), ctx: Ctx = Depends(get_ctx)):
    data = await read_upload(file, ctx.settings.max_image_bytes)
    img = await run_in_threadpool(validate_image_bytes, data, ctx.settings.max_image_bytes)
    return ok(await ctx.food.analyze(img, grams))


@router.post("/manual", summary="Nutrition estimate for a food chosen by name (no image model)")
async def manual(body: FoodManualRequest, ctx: Ctx = Depends(get_ctx)):
    return ok(ctx.food.manual(body.label, body.grams))


@router.get("/reference", summary="Foods available in the bundled nutrition reference")
async def reference():
    return ok(nutrition.list_foods())
