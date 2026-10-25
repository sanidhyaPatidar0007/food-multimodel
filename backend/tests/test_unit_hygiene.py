import asyncio

import pytest

from app.services import hygiene as h
from app.utils.errors import MediaError, ProviderError

from tests.helpers import make_video_bytes

import numpy as np

FRAMES = [h.Frame(i, float(i), (np.random.default_rng(i).normal(128, 50, (240, 320, 3))).clip(0, 255).astype("uint8")) for i in range(4)]
META = {"source": "test"}


class Fake:
    name = "fake"

    def __init__(self, mapping):
        self.mapping = mapping

    async def analyze(self, frames):
        return self.mapping


def status_dict(**kw):
    out = {k: {"status": "not_assessed", "severity": None, "observations": []} for k in h.DEFAULT_CRITERIA}
    for k, (st, sev) in kw.items():
        out[k] = {"status": st, "severity": sev, "observations": []}
    return out


def test_frame_extraction_intervals_and_metadata():
    frames, meta = h.frames_from_video_bytes(make_video_bytes(6, 10), ".avi", interval_s=2.0, max_frames=24)
    assert [f.timestamp_s for f in frames] == [0.0, 2.0, 4.0]
    assert meta["fps"] == 10.0 and meta["frames_extracted"] == 3
    frames, _ = h.frames_from_video_bytes(make_video_bytes(6, 10), ".avi", interval_s=1.0, max_frames=2)
    assert len(frames) == 2


def test_invalid_and_overlong_video_rejected():
    with pytest.raises(MediaError):
        h.frames_from_video_bytes(b"RIFF....AVI garbage not a real video", ".avi")
    with pytest.raises(MediaError):
        h.frames_from_video_bytes(make_video_bytes(6, 10), ".avi", max_seconds=3)
    for bad in (0.0, 0.05, 61):
        with pytest.raises(MediaError):
            h.frames_from_video_bytes(make_video_bytes(1, 10), ".avi", interval_s=bad)


def test_temp_file_is_deleted(tmp_path=None):
    import glob, tempfile
    before = set(glob.glob(tempfile.gettempdir() + "/tmp*.avi"))
    h.frames_from_video_bytes(make_video_bytes(1, 10), ".avi")
    try:
        h.frames_from_video_bytes(b"junk", ".avi")
    except MediaError:
        pass
    assert set(glob.glob(tempfile.gettempdir() + "/tmp*.avi")) == before


def test_without_detector_nothing_is_claimed():
    rep = asyncio.run(h.assess(FRAMES, META, h.NullDetector()))
    assert rep["status"] == "detector_unavailable"
    assert rep["score"]["score"] is None and rep["score"]["rating"] == "insufficient_evidence"
    assert all(c["status"] == "not_assessed" for c in rep["criteria"].values())
    assert rep["issues"] == [] and rep["unobservable_criteria"]
    assert "not an official" in rep["disclaimer"].lower()


def test_score_boundaries():
    cfg = h.HygieneConfig()
    assert h.score(status_dict(**{k: ("pass", None) for k in h.DEFAULT_CRITERIA}), cfg)["score"] == 100.0
    assert h.score(status_dict(**{k: ("violation", "high") for k in h.DEFAULT_CRITERIA}), cfg)["score"] == 0.0
    assert h.score(status_dict(), cfg)["score"] is None


def test_coverage_threshold_boundaries():
    cfg = h.HygieneConfig(weights={"hair_covering": 40, "protective_equipment": 0, "food_handling": 0, "surface_cleanliness": 60, "cross_contamination": 0})
    just_under = h.score(status_dict(hair_covering=("pass", None)), h.HygieneConfig(weights=cfg.weights, min_coverage=0.41))
    at_limit = h.score(status_dict(hair_covering=("pass", None)), h.HygieneConfig(weights=cfg.weights, min_coverage=0.4))
    assert just_under["score"] is None and at_limit["score"] == 100.0


def test_rating_band_edges_are_inclusive():
    crit = status_dict(hair_covering=("violation", "medium"))
    base = dict(weights={"hair_covering": 100, "protective_equipment": 0, "food_handling": 0, "surface_cleanliness": 0, "cross_contamination": 0}, min_coverage=0.0)
    s = h.score(crit, h.HygieneConfig(**base))["score"]
    assert s == 33.0
    assert h.score(crit, h.HygieneConfig(**base, band_attention=33.0, band_good=90))["rating"] == "needs_attention"
    assert h.score(crit, h.HygieneConfig(**base, band_attention=33.1, band_good=90))["rating"] == "poor"
    assert h.score(status_dict(hair_covering=("pass", None)), h.HygieneConfig(**base))["rating"] == "good"


def test_severity_ordering_and_mixed_criteria_math():
    mapping = {0: [h.Finding("hair_covering", "violation", "medium", "no cap"), h.Finding("surface_cleanliness", "pass")],
               1: [h.Finding("protective_equipment", "pass"), h.Finding("hair_covering", "violation", "high", "again")]}
    rep = asyncio.run(h.assess(FRAMES, META, Fake(mapping)))
    assert rep["criteria"]["hair_covering"]["severity"] == "high"
    # assessed weight 15+25+15=55, penalty 15*1.0 -> 100*(1-15/55)=72.7
    assert rep["score"]["score"] == 72.7 and rep["score"]["rating"] == "poor"
    assert rep["issues"][0]["severity"] == "high"
    assert rep["corrective_actions"] and "hair" in rep["corrective_actions"][0].lower()
    assert "Preliminary" in rep["report_markdown"]


def test_violation_beats_pass_regardless_of_frame_order():
    m = {0: [h.Finding("food_handling", "pass")], 1: [h.Finding("food_handling", "violation", "low", "x")], 2: [h.Finding("food_handling", "pass")]}
    assert h.aggregate(m, FRAMES)["food_handling"]["status"] == "violation"


def test_unusable_frames_are_skipped_and_reported():
    black = [h.Frame(0, 0.0, np.zeros((240, 320, 3), dtype="uint8"))]
    rep = asyncio.run(h.assess(black, META, Fake({})))
    assert rep["status"] == "no_usable_frames" and rep["score"]["score"] is None
    assert any("skipped" in n for n in rep["notes"])


def test_detector_error_is_reported_not_raised():
    class Boom:
        name = "boom"
        async def analyze(self, frames):
            raise ProviderError("The AI provider timed out. Please try again.")
    rep = asyncio.run(h.assess(FRAMES, META, Boom()))
    assert rep["status"] == "detector_error" and "timed out" in rep["detector_error"]


def test_detector_json_parsing_ignores_garbage():
    parsed = h.parse_detector_json({"frames": [
        {"index": 0, "findings": [{"criterion": "hair_covering", "status": "violation", "severity": "bogus", "evidence": "x"},
                                  {"criterion": "made_up", "status": "pass"}, {"criterion": "food_handling", "status": "maybe"}]},
        {"index": 99, "findings": [{"criterion": "hair_covering", "status": "pass"}]}]}, valid_indices={0, 1})
    assert list(parsed) == [0] and len(parsed[0]) == 1 and parsed[0][0].severity == "low"
    with pytest.raises(ProviderError):
        h.parse_detector_json({"nope": 1}, {0})


def test_config_validation():
    for bad in (h.HygieneConfig(weights={"x": 1}), h.HygieneConfig(weights={k: 0 for k in h.DEFAULT_CRITERIA}),
                h.HygieneConfig(min_coverage=2), h.HygieneConfig(band_attention=95, band_good=90)):
        with pytest.raises(MediaError):
            bad.validate()
