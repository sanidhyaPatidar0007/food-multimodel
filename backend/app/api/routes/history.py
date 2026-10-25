from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query

from app.api.routes.common import ok
from app.api.schemas import HistoryCreate
from app.database.repository import KINDS
from app.deps import Ctx, get_ctx
from app.services import dashboard
from app.utils.errors import AppError, NotFound

router = APIRouter(tags=["history"])


@router.get("/history", summary="Saved records, newest first (empty list when nothing saved)")
async def list_history(kind: str | None = Query(default=None), limit: int = Query(default=50, ge=1, le=200),
                       offset: int = Query(default=0, ge=0), ctx: Ctx = Depends(get_ctx)):
    if kind and kind not in KINDS:
        raise AppError(f"Unknown kind '{kind}'.", details={"allowed": sorted(KINDS)})
    return ok(ctx.repo.list(kind, limit, offset), total=ctx.repo.count(kind), limit=limit, offset=offset)


@router.post("/history", summary="Save an analysis result you chose to keep", status_code=201)
async def save(body: HistoryCreate, ctx: Ctx = Depends(get_ctx)):
    payload = {k: v for k, v in body.payload.items() if k not in ("previews", "report_markdown")} if body.kind == "hygiene_report" else body.payload
    return ok(ctx.repo.add(body.kind, payload))


@router.get("/history/{record_id}")
async def get_one(record_id: str, ctx: Ctx = Depends(get_ctx)):
    rec = ctx.repo.get(record_id)
    if not rec:
        raise NotFound("Record not found.")
    return ok(rec)


@router.delete("/history/{record_id}")
async def delete(record_id: str, ctx: Ctx = Depends(get_ctx)):
    if not ctx.repo.delete(record_id):
        raise NotFound("Record not found.")
    return ok({"deleted": record_id})


@router.get("/dashboard/summary", summary="Aggregated dashboard data (empty sections when there is no data)")
async def dashboard_summary(today: date | None = Query(default=None, description="Client's local date (YYYY-MM-DD)"),
                            ctx: Ctx = Depends(get_ctx)):
    if today is not None and abs((today - date.today()).days) > 2:  # accept any real timezone offset, reject nonsense
        raise AppError("`today` must be within two days of the server date.")
    return ok(dashboard.summary(ctx.repo, today))
