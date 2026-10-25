from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends

from app.api.routes.common import ok
from app.api.schemas import GeneratePlanRequest, IntakeLog, ProfileIn, ReplaceMealRequest, ShoppingToggle
from app.deps import Ctx, get_ctx, run_in_threadpool
from app.services import meal_planner as mp
from app.utils.errors import AppError, NotFound

router = APIRouter(prefix="/meal-planner", tags=["meal-planner"])
PROFILE_ID = "profile-default"


def _profile(ctx: Ctx) -> dict:
    rec = ctx.repo.get(PROFILE_ID)
    if not rec:
        raise NotFound("No profile saved yet. Save your preferences first.")
    return rec["payload"]


def _plan_rec(ctx: Ctx, plan_id: str) -> dict:
    rec = ctx.repo.get(plan_id)
    if not rec or rec["kind"] != "meal_plan":
        raise NotFound("Meal plan not found.")
    return rec


@router.post("/profile", summary="Validate and save dietary preferences")
async def save_profile(body: ProfileIn, ctx: Ctx = Depends(get_ctx)):
    data = body.model_dump()
    targets = mp.compute_targets(data)  # also validates goal / age combinations
    known, free = mp.normalize_allergies(data["allergies"])
    ctx.repo.upsert("profile", PROFILE_ID, data)
    return ok({"profile": data, "targets": targets, "recognised_allergens": sorted(known), "free_text_allergens": free,
               "disclaimer": mp.DISCLAIMER})


@router.get("/profile")
async def get_profile(ctx: Ctx = Depends(get_ctx)):
    rec = ctx.repo.get(PROFILE_ID)
    return ok(rec["payload"] if rec else None)


@router.get("/options", summary="Allergen vocabulary and selectable values")
async def options():
    return ok({"allergens": mp.ALLERGENS, "diets": mp.DIETS, "goals": mp.GOALS, "activity_levels": list(mp.ACTIVITY),
               "age_ranges": mp.AGE_RANGES, "cuisines": sorted({m["cuisine"] for m in mp.library()})})


@router.post("/generate", summary="Generate a daily or weekly plan (allergy exclusions are mandatory filters)")
async def generate(body: GeneratePlanRequest, ctx: Ctx = Depends(get_ctx)):
    if body.profile is not None:
        profile = body.profile.model_dump()
        ctx.repo.upsert("profile", PROFILE_ID, profile)
    else:
        profile = _profile(ctx)
    plan = await run_in_threadpool(mp.generate_plan, profile, body.days, body.seed)
    rec = ctx.repo.add("meal_plan", plan)
    return ok({"id": rec["id"], "created_at": rec["created_at"], "plan": plan})


@router.get("", summary="Latest saved meal plan (data is null if none exists)")
async def latest(ctx: Ctx = Depends(get_ctx)):
    rec = ctx.repo.latest("meal_plan")
    return ok({"id": rec["id"], "created_at": rec["created_at"], "plan": rec["payload"]} if rec else None)


@router.post("/replace", summary="Replace one meal (re-checked against exclusions)")
async def replace(body: ReplaceMealRequest, ctx: Ctx = Depends(get_ctx)):
    rec = _plan_rec(ctx, body.plan_id)
    plan = mp.replace_meal(rec["payload"], _profile(ctx), body.day, body.slot, body.meal_id)
    ctx.repo.upsert("meal_plan", body.plan_id, plan)
    return ok({"id": body.plan_id, "plan": plan})


@router.patch("/shopping", summary="Mark a shopping-list item purchased / not purchased")
async def toggle_item(body: ShoppingToggle, ctx: Ctx = Depends(get_ctx)):
    rec = _plan_rec(ctx, body.plan_id)
    plan = rec["payload"]
    item = next((i for i in plan["shopping_list"] if i["key"] == body.key), None)
    if item is None:
        raise NotFound("Shopping item not found.")
    item["purchased"] = body.purchased
    ctx.repo.upsert("meal_plan", body.plan_id, plan)
    return ok({"id": body.plan_id, "shopping_list": plan["shopping_list"]})


@router.post("/log", summary="Log eaten food towards today's nutrition progress")
async def log_intake(body: IntakeLog, ctx: Ctx = Depends(get_ctx)):
    d = (body.date or date.today()).isoformat()
    # Clients can be up to a day ahead of the server clock (e.g. India vs. a UTC host), so allow +1 day.
    if d > (date.today() + timedelta(days=1)).isoformat():
        raise AppError("You cannot log intake for a future date.")
    rec = ctx.repo.add("intake_log", {**body.model_dump(mode="json"), "date": d})
    return ok(rec)
