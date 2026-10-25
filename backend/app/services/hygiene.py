"""Restaurant / kitchen hygiene assessment (preliminary visual review, NOT an inspection).

Pipeline: validate media -> extract frames (OpenCV) -> per-frame quality check (deterministic)
-> detector (pluggable; only real detector output becomes a finding) -> aggregate per criterion
-> configurable score -> report.

With no detector configured every observable criterion is reported as "not_assessed" and the
score is null. Nothing is inferred or invented.
"""
from __future__ import annotations

import asyncio
import logging
import os
import tempfile
from dataclasses import dataclass, field
from typing import Protocol

import cv2
import numpy as np

from app.services.llm import LLM, extract_json, has_vision
from app.utils.errors import MediaError, ProviderError, ProviderUnavailable
from app.utils.imaging import bgr_to_jpeg_b64, quality_report

log = logging.getLogger("foodverse.hygiene")

SEVERITY_FACTOR = {"low": 0.34, "medium": 0.67, "high": 1.0}

# Criteria a camera *can* plausibly show, with default weights (sum = 100).
DEFAULT_CRITERIA = {
    "hair_covering": {"label": "Hair covering worn where required", "weight": 15},
    "protective_equipment": {"label": "Gloves / protective equipment where applicable", "weight": 15},
    "food_handling": {"label": "Safe food-handling practices", "weight": 20},
    "surface_cleanliness": {"label": "Visible cleanliness of food-contact surfaces", "weight": 25},
    "cross_contamination": {"label": "No visible cross-contamination indicators", "weight": 25},
}
# Things an inspection checks that video generally cannot show.
UNOBSERVABLE = [
    "Hand-washing frequency and technique",
    "Food and fridge temperatures",
    "Pest control and storage conditions out of frame",
    "Staff training, records and allergen management systems",
    "Chemical storage and cleaning-product concentration",
]
DISCLAIMER = ("Preliminary visual assessment only. It is not an official food-safety inspection and does not "
              "certify compliance. Only criteria listed as assessed were considered; others are unknown.")


@dataclass
class HygieneConfig:
    weights: dict[str, float] = field(default_factory=lambda: {k: float(v["weight"]) for k, v in DEFAULT_CRITERIA.items()})
    min_coverage: float = 0.4          # share of total weight that must be assessed to produce a score
    band_good: float = 90.0
    band_attention: float = 75.0

    def validate(self) -> None:
        unknown = set(self.weights) - set(DEFAULT_CRITERIA)
        if unknown:
            raise MediaError(f"Unknown hygiene criteria: {sorted(unknown)}")
        if any(w < 0 or w > 100 for w in self.weights.values()) or sum(self.weights.values()) <= 0:
            raise MediaError("Criterion weights must be between 0 and 100 and not all zero.")
        if not 0 <= self.min_coverage <= 1:
            raise MediaError("min_coverage must be between 0 and 1.")
        if not self.band_attention < self.band_good <= 100:
            raise MediaError("Score bands must satisfy attention < good <= 100.")


@dataclass
class Frame:
    index: int
    timestamp_s: float
    bgr: np.ndarray


@dataclass
class Finding:
    criterion: str
    status: str            # "pass" | "violation" | "not_visible"
    severity: str = "low"  # for violations: low | medium | high
    evidence: str = ""


class HygieneDetector(Protocol):
    name: str
    async def analyze(self, frames: list[Frame]) -> dict[int, list[Finding]]: ...


class NullDetector:
    """Default: performs no visual detection."""
    name = "none"

    async def analyze(self, frames: list[Frame]) -> dict[int, list[Finding]]:
        raise ProviderUnavailable("No hygiene vision detector is configured. Set LLM_PROVIDER/LLM_API_KEY or plug in your own detector.")


LLM_SYSTEM = (
    "You review kitchen video frames for a PRELIMINARY hygiene screening. For each numbered frame and each criterion "
    "report only what is clearly visible. Criteria ids: " + ", ".join(DEFAULT_CRITERIA) + ". "
    'Respond with JSON only: {"frames":[{"index":<int>,"findings":[{"criterion":"<id>","status":"pass|violation|not_visible",'
    '"severity":"low|medium|high","evidence":"<what you can see>"}]}]}. '
    "Use not_visible whenever people/surfaces are absent, too small, blurry or out of frame. Never assume. "
    "Severity applies only to violations. Describe visual evidence, not conclusions about legal compliance."
)


class LLMHygieneDetector:
    name = "llm_vision"

    def __init__(self, llm: LLM, max_frames: int = 8):
        self.llm, self.max_frames = llm, max_frames

    async def analyze(self, frames: list[Frame]) -> dict[int, list[Finding]]:
        if not has_vision(self.llm):
            raise ProviderUnavailable("LLM vision is not configured. Set LLM_VISION_MODEL to a vision-capable model.")
        chosen = frames[:: max(1, len(frames) // self.max_frames)][: self.max_frames]
        imgs = [bgr_to_jpeg_b64(f.bgr, 896) for f in chosen]
        order = ", ".join(f"image {i + 1} = frame index {f.index} at {f.timestamp_s:.1f}s" for i, f in enumerate(chosen))
        raw = await self.llm.complete(LLM_SYSTEM, [{"role": "user", "content": f"Frames in order: {order}. Analyse them."}],
                                      images_b64=imgs, max_tokens=4000)
        return parse_detector_json(extract_json(raw), valid_indices={f.index for f in chosen})


def parse_detector_json(data: dict, valid_indices: set[int]) -> dict[int, list[Finding]]:
    out: dict[int, list[Finding]] = {}
    if not isinstance(data, dict) or not isinstance(data.get("frames"), list):
        raise ProviderError("The vision model returned an unexpected structure.")
    for fr in data["frames"]:
        try:
            idx = int(fr["index"])
        except (KeyError, TypeError, ValueError):  # missing/odd index, or a frame entry that is not an object
            continue
        if idx not in valid_indices:
            continue
        for f in fr.get("findings") or []:
            if not isinstance(f, dict):
                continue
            crit, status = f.get("criterion"), f.get("status")
            if crit not in DEFAULT_CRITERIA or status not in {"pass", "violation", "not_visible"}:
                continue
            sev = f.get("severity") if f.get("severity") in SEVERITY_FACTOR else "low"
            out.setdefault(idx, []).append(Finding(crit, status, sev, str(f.get("evidence", ""))[:300]))
    return out


# ---------------- frame extraction ----------------

def extract_frames(path: str, interval_s: float = 2.0, max_frames: int = 24, max_seconds: float = 120) -> tuple[list[Frame], dict]:
    if not 0.1 <= interval_s <= 60:
        raise MediaError("Frame interval must be between 0.1 and 60 seconds.")
    if not 1 <= max_frames <= 120:
        raise MediaError("max_frames must be between 1 and 120.")
    cap = cv2.VideoCapture(path)
    try:
        if not cap.isOpened():
            raise MediaError("The video could not be opened; it may be corrupted or use an unsupported codec.")
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if fps <= 0 or fps > 240:
            fps = 25.0  # container did not report a sane fps; assume 25 and say so
            fps_assumed = True
        else:
            fps_assumed = False
        duration = total / fps if total > 0 else 0.0
        if duration > max_seconds:
            raise MediaError(f"Video is {duration:.0f}s long; the limit is {max_seconds:.0f}s. Trim it and retry.")
        step = max(1, round(fps * interval_s))
        frames: list[Frame] = []
        i = 0
        while len(frames) < max_frames:
            ok, bgr = cap.read()
            if not ok:
                break
            if i % step == 0:
                frames.append(Frame(len(frames), round(i / fps, 2), bgr))
            i += 1
            if i / fps > max_seconds:
                break
        if not frames:
            raise MediaError("No frames could be read from the video.")
        h, w = frames[0].bgr.shape[:2]
        meta = {"fps": round(fps, 2), "fps_assumed": fps_assumed, "duration_s": round(duration, 2), "width": w, "height": h,
                "interval_s": interval_s, "frames_extracted": len(frames)}
        return frames, meta
    finally:
        cap.release()


def frames_from_video_bytes(data: bytes, suffix: str, **kw) -> tuple[list[Frame], dict]:
    """Write to a temp file (OpenCV needs a path), extract, and always delete the file."""
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        return extract_frames(path, **kw)
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def thumbnail(frame: Frame, max_side: int = 320) -> dict:
    return {"index": frame.index, "timestamp_s": frame.timestamp_s, "jpeg_b64": bgr_to_jpeg_b64(frame.bgr, max_side, 70)}


# ---------------- scoring ----------------

def aggregate(findings_by_frame: dict[int, list[Finding]], frames: list[Frame]) -> dict[str, dict]:
    ts = {f.index: f.timestamp_s for f in frames}
    res = {k: {"status": "not_assessed", "severity": None, "observations": []} for k in DEFAULT_CRITERIA}
    for idx, fl in findings_by_frame.items():
        for f in fl:
            r = res[f.criterion]
            if f.status == "violation":
                if r["status"] != "violation" or SEVERITY_FACTOR[f.severity] > SEVERITY_FACTOR[r["severity"]]:
                    r["severity"] = f.severity
                r["status"] = "violation"
                r["observations"].append({"frame": idx, "timestamp_s": ts.get(idx), "severity": f.severity, "evidence": f.evidence})
            elif f.status == "pass" and r["status"] != "violation":
                r["status"] = "pass"
    return res


def score(criteria: dict[str, dict], cfg: HygieneConfig) -> dict:
    total_w = sum(cfg.weights.values())
    assessed_w = sum(cfg.weights[k] for k, v in criteria.items() if v["status"] != "not_assessed")
    coverage = assessed_w / total_w if total_w else 0.0
    if assessed_w == 0 or coverage < cfg.min_coverage:
        return {"score": None, "rating": "insufficient_evidence", "coverage": round(coverage, 3),
                "message": f"Only {coverage:.0%} of the weighted criteria could be assessed (minimum {cfg.min_coverage:.0%}); no score is given."}
    penalty = sum(cfg.weights[k] * SEVERITY_FACTOR[v["severity"]] for k, v in criteria.items() if v["status"] == "violation")
    value = round(max(0.0, min(100.0, 100.0 * (1 - penalty / assessed_w))), 1)
    rating = "good" if value >= cfg.band_good else "needs_attention" if value >= cfg.band_attention else "poor"
    return {"score": value, "rating": rating, "coverage": round(coverage, 3), "message": None}


def corrective_actions(criteria: dict[str, dict]) -> list[str]:
    tips = {
        "hair_covering": "Require hair restraints (cap or net) for everyone handling food.",
        "protective_equipment": "Provide and enforce gloves/aprons where the task requires them; change them between tasks.",
        "food_handling": "Retrain staff on safe handling; keep ready-to-eat food from bare-hand contact where required.",
        "surface_cleanliness": "Clean and sanitise food-contact surfaces and equipment; verify with the cleaning schedule.",
        "cross_contamination": "Separate raw and ready-to-eat foods, use colour-coded boards/utensils, sanitise between tasks.",
    }
    return [tips[k] for k, v in criteria.items() if v["status"] == "violation"]


def report_markdown(report: dict) -> str:
    s = report["score"]
    lines = ["# Preliminary Kitchen Hygiene Review", "",
             f"**Score:** {s['score'] if s['score'] is not None else 'not available'}  |  **Rating:** {s['rating']}  |  **Evidence coverage:** {s['coverage']:.0%}", ""]
    if s.get("message"):
        lines += [f"> {s['message']}", ""]
    lines += ["## Criteria", ""]
    for k, v in report["criteria"].items():
        lines.append(f"- **{DEFAULT_CRITERIA[k]['label']}** - {v['status']}" + (f" ({v['severity']})" if v["severity"] else ""))
        for o in v["observations"]:
            lines.append(f"    - {o['timestamp_s']}s (frame {o['frame']}): {o['evidence']}")
    lines += ["", "## Recommended corrective actions", ""] + ([f"- {a}" for a in report["corrective_actions"]] or ["- None identified from assessed criteria."])
    lines += ["", "## Not observable from video", ""] + [f"- {u}" for u in report["unobservable_criteria"]]
    lines += ["", f"_{DISCLAIMER}_", ""]
    return "\n".join(lines)


async def assess(frames: list[Frame], meta: dict, detector: HygieneDetector, cfg: HygieneConfig | None = None) -> dict:
    cfg = cfg or HygieneConfig()
    cfg.validate()
    quality = []
    usable: list[Frame] = []
    for f in frames:
        q = quality_report(f.bgr)
        quality.append({"frame": f.index, "timestamp_s": f.timestamp_s, **{k: q[k] for k in ("sharpness", "brightness", "usable", "warnings")}})
        if q["usable"]:
            usable.append(f)
    status, detector_error = "ok", None
    findings: dict[int, list[Finding]] = {}
    if not usable:
        status = "no_usable_frames"
    else:
        try:
            findings = await detector.analyze(usable)
        except ProviderUnavailable as exc:
            status, detector_error = "detector_unavailable", exc.message
        except ProviderError as exc:
            status, detector_error = "detector_error", exc.message
    criteria = aggregate(findings, frames)
    sc = score(criteria, cfg)
    issues = []
    for k, v in criteria.items():
        for o in v["observations"]:
            issues.append({"criterion": k, "label": DEFAULT_CRITERIA[k]["label"], **o})
    issues.sort(key=lambda i: (-SEVERITY_FACTOR[i["severity"]], i["timestamp_s"] or 0))
    notes = []
    if status == "detector_unavailable":
        notes.append("Frames were extracted and quality-checked, but no vision detector is configured, so no hygiene criteria were assessed.")
    for q in quality:
        if not q["usable"]:
            notes.append(f"Frame at {q['timestamp_s']}s skipped: {q['warnings'][0]}")
    report = {
        "status": status, "detector": detector.name, "detector_error": detector_error, "video": meta,
        "score": sc, "criteria": {k: {**v, "label": DEFAULT_CRITERIA[k]["label"], "weight": cfg.weights[k]} for k, v in criteria.items()},
        "issues": issues, "corrective_actions": corrective_actions(criteria), "unobservable_criteria": UNOBSERVABLE,
        "frame_quality": quality, "notes": notes, "config": {"weights": cfg.weights, "min_coverage": cfg.min_coverage,
                                                              "band_good": cfg.band_good, "band_attention": cfg.band_attention},
        "disclaimer": DISCLAIMER,
    }
    report["report_markdown"] = report_markdown(report)
    return report


def build_detector(llm: LLM, settings=None) -> HygieneDetector:
    return LLMHygieneDetector(llm) if has_vision(llm) else NullDetector()
