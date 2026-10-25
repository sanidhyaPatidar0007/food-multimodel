from fastapi import APIRouter, Depends, File, UploadFile

from app.api.routes.common import ok
from app.api.schemas import ChatRequest, RecipeRequest, ScaleRequest
from app.deps import Ctx, get_ctx, read_upload, run_in_threadpool
from app.services.kitchen import scale_recipe
from app.services.llm import has_vision
from app.utils.errors import MediaError, ProviderUnavailable
from app.utils.imaging import to_jpeg_b64
from app.utils.media import validate_image_bytes

router = APIRouter(prefix="/kitchen", tags=["kitchen"])


@router.post("/recipe", summary="Generate recipes (LLM, or clearly labelled local fallback)")
async def recipe(body: RecipeRequest, ctx: Ctx = Depends(get_ctx)):
    return ok(await ctx.kitchen.recipes(ingredients=body.ingredients, equipment=body.equipment, diet=body.diet,
                                        restrictions=list(body.restrictions), avoid=body.avoid, dish=body.dish,
                                        servings=body.servings, notes=body.notes))


@router.post("/chat", summary="Follow-up cooking questions")
async def chat(body: ChatRequest, ctx: Ctx = Depends(get_ctx)):
    return ok(await ctx.kitchen.chat([m.model_dump() for m in body.messages], body.recipe))


@router.post("/scale", summary="Rescale ingredient quantities (deterministic)")
async def scale(body: ScaleRequest):
    r = body.recipe
    if (not isinstance(r.get("ingredients"), list) or not all(isinstance(i, dict) for i in r["ingredients"])
            or not isinstance(r.get("servings"), int) or isinstance(r.get("servings"), bool) or r["servings"] < 1):
        raise MediaError("recipe must include 'ingredients' (a list of objects) and a positive integer 'servings'.")
    return ok(scale_recipe(r, body.servings))


@router.post("/ingredients/scan", summary="Identify ingredients in photos (needs a vision-capable LLM)")
async def scan(files: list[UploadFile] = File(...), ctx: Ctx = Depends(get_ctx)):
    if not has_vision(ctx.llm):
        raise ProviderUnavailable("Ingredient photos need a vision-capable LLM. Set LLM_PROVIDER, LLM_API_KEY and (for Groq/OpenRouter) LLM_VISION_MODEL, or type your ingredients.")
    if not 1 <= len(files) <= 4:
        raise MediaError("Upload between 1 and 4 images.")
    imgs = []
    for f in files:
        data = await read_upload(f, ctx.settings.max_image_bytes)
        imgs.append(to_jpeg_b64(await run_in_threadpool(validate_image_bytes, data, ctx.settings.max_image_bytes)))
    return ok(await ctx.kitchen.scan_ingredients(imgs))
