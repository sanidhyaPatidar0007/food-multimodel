from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Form, UploadFile

from app.api.routes.common import ok
from app.deps import Ctx, get_ctx, read_upload, run_in_threadpool
from app.services import hygiene as hy
from app.utils.errors import AppError, MediaError
from app.utils.imaging import pil_to_bgr
from app.utils.media import sniff_video, validate_image_bytes, validate_video_bytes

router = APIRouter(prefix="/hygiene", tags=["hygiene"])
SUFFIX = {"video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov", "video/x-msvideo": ".avi"}


async def _frames(files: list[UploadFile], interval: float, max_frames: int, ctx: Ctx) -> tuple[list[hy.Frame], dict]:
    if not files:
        raise MediaError("Upload one short video or one or more images.")
    first = await read_upload(files[0], ctx.settings.max_video_bytes)
    if sniff_video(first):
        if len(files) > 1:
            raise MediaError("Upload either a single video or several images, not both.")
        kind = validate_video_bytes(first, ctx.settings.max_video_bytes)
        frames, meta = await run_in_threadpool(
            lambda: hy.frames_from_video_bytes(first, SUFFIX[kind], interval_s=interval, max_frames=max_frames,
                                               max_seconds=ctx.settings.max_video_seconds))
        meta["source"] = "video"
        return frames, meta
    if len(files) > 24:
        raise MediaError("At most 24 images can be analysed at once.")
    frames = []
    blobs = [first] + [await read_upload(f, ctx.settings.max_image_bytes) for f in files[1:]]
    for i, blob in enumerate(blobs):
        img = await run_in_threadpool(validate_image_bytes, blob, ctx.settings.max_image_bytes)
        frames.append(hy.Frame(i, float(i), pil_to_bgr(img)))
    h, w = frames[0].bgr.shape[:2]
    return frames, {"source": "images", "frames_extracted": len(frames), "width": w, "height": h, "interval_s": None,
                    "fps": None, "fps_assumed": False, "duration_s": None}


def _config(raw: str | None) -> hy.HygieneConfig:
    cfg = hy.HygieneConfig()
    if raw:
        try:
            data = json.loads(raw)
            if not isinstance(data, dict):
                raise ValueError
            if "weights" in data:
                cfg.weights = {**cfg.weights, **{k: float(v) for k, v in data["weights"].items()}}
            for k in ("min_coverage", "band_good", "band_attention"):
                if k in data:
                    setattr(cfg, k, float(data[k]))
        except (ValueError, TypeError, AttributeError):
            raise AppError("config must be a JSON object like {\"weights\":{...},\"min_coverage\":0.4}.")
    cfg.validate()
    return cfg


@router.get("/criteria", summary="Default scoring criteria and weights")
async def criteria():
    return ok({"criteria": hy.DEFAULT_CRITERIA, "unobservable": hy.UNOBSERVABLE, "disclaimer": hy.DISCLAIMER,
               "defaults": {"min_coverage": 0.4, "band_good": 90, "band_attention": 75}})


@router.post("/frames", summary="Extract preview frames without analysing them")
async def preview_frames(files: list[UploadFile] = File(...), interval_seconds: float = Form(default=2.0, ge=0.1, le=60),
                         max_frames: int = Form(default=12, ge=1, le=120), ctx: Ctx = Depends(get_ctx)):
    frames, meta = await _frames(files, interval_seconds, max_frames, ctx)
    return ok({"video": meta, "frames": [hy.thumbnail(f) for f in frames]})


@router.post("/analyze", summary="Preliminary hygiene screening of a video or images")
async def analyze(files: list[UploadFile] = File(...), interval_seconds: float | None = Form(default=None, ge=0.1, le=60),
                  max_frames: int | None = Form(default=None, ge=1, le=120), config: str | None = Form(default=None),
                  ctx: Ctx = Depends(get_ctx)):
    cfg = _config(config)
    frames, meta = await _frames(files, interval_seconds or ctx.settings.hygiene_frame_interval_seconds,
                                 max_frames or ctx.settings.hygiene_max_frames, ctx)
    report = await hy.assess(frames, meta, ctx.hygiene_detector, cfg)
    flagged = {i["frame"] for i in report["issues"]}
    report["previews"] = [hy.thumbnail(f) for f in frames if f.index in flagged][:8] or [hy.thumbnail(f) for f in frames[:4]]
    return ok(report)
