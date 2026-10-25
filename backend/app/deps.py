"""Service container and FastAPI dependencies."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Request, UploadFile
from starlette.concurrency import run_in_threadpool  # noqa: F401  (re-exported for routes)

from app.config import Settings
from app.database.repository import Repository
from app.services.food_recognition import FoodRecognizer
from app.services.freshness import FreshnessService
from app.services.hygiene import HygieneDetector, build_detector
from app.services.kitchen import KitchenService
from app.services.llm import LLM


@dataclass
class Ctx:
    settings: Settings
    repo: Repository
    llm: LLM
    food: FoodRecognizer
    freshness: FreshnessService
    kitchen: KitchenService
    hygiene_detector: HygieneDetector


def build_ctx(settings: Settings, repo: Repository, llm: LLM) -> Ctx:
    return Ctx(settings, repo, llm, FoodRecognizer(settings, llm), FreshnessService(settings, llm=llm), KitchenService(llm), build_detector(llm))


def get_ctx(request: Request) -> Ctx:
    return request.app.state.ctx


async def read_upload(file: UploadFile, limit: int) -> bytes:
    """Read at most limit+1 bytes so oversize files are detected without buffering them fully."""
    return await file.read(limit + 1)
