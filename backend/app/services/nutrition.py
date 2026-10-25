"""Deterministic nutrition lookup, scaling, uncertainty and health scoring.

Everything here is *calculation over a reference table* -- not AI inference.
Outputs are estimates and are labelled as such.
"""
from __future__ import annotations

import difflib
import re
from functools import lru_cache

from app.data.nutrition_reference import DATASET_NAME, load_rows
from app.utils.errors import AppError

PORTION_UNCERTAINTY_ASSUMED = 0.30   # +/- when the serving size is only assumed
PORTION_UNCERTAINTY_GIVEN = 0.10     # +/- when the user supplied grams (dataset variability only)
DISCLAIMER = ("Nutrition values are estimates derived from a reference table and an assumed or "
              "user-provided portion. They are not measurements and not medical advice.")


@lru_cache
def _table() -> dict[str, dict]:
    return {r["key"]: r for r in load_rows()}


@lru_cache
def _alias_index() -> dict[str, str]:
    idx: dict[str, str] = {}
    for key, row in _table().items():
        for term in [key.replace("_", " "), row["name"].lower(), *[a.lower() for a in row["aliases"]]]:
            idx[term] = key
    return idx


def _norm(text: str) -> str:
    return re.sub(r"[^a-z ]", " ", text.lower()).strip()


def list_foods() -> list[dict]:
    return [{"key": r["key"], "name": r["name"], "category": r["category"]} for r in _table().values()]


# Words that do not change *which food* it is. Any other leftover word (e.g. "beet" in "beet salad")
# blocks a containment match, so we never attach another food's nutrition to a different dish.
NEUTRAL_WORDS = {"a", "an", "the", "of", "with", "and", "grilled", "fried", "baked", "roasted", "cooked", "boiled", "steamed",
                 "fresh", "homemade", "slice", "slices", "piece", "pieces", "plate", "bowl", "serving", "portion", "cup", "whole", "small", "large"}


def find_food(label: str, cutoff: float = 0.78) -> str | None:
    """Map a free-text label to a reference key, or None if no confident match."""
    text = " ".join(_norm(label).split())
    if not text:
        return None
    idx = _alias_index()
    if text in idx:
        return idx[text]
    # whole-word containment, longest term first ("grilled chicken breast" -> grilled_chicken)
    padded = f" {text} "
    for term in sorted(idx, key=len, reverse=True):
        if f" {term} " in padded:
            leftover = set(padded.replace(f" {term} ", " ").split()) - NEUTRAL_WORDS
            if not leftover:
                return idx[term]
    close = difflib.get_close_matches(text, list(idx), n=1, cutoff=cutoff)
    return idx[close[0]] if close else None


def _scale(row: dict, grams: float) -> dict:
    f = grams / 100.0
    out = {k: round(row[k] * f, 1) for k in ("kcal", "protein_g", "carbs_g", "fat_g", "fiber_g", "sugar_g", "sat_fat_g")}
    out["sodium_mg"] = round(row["sodium_mg"] * f)
    out["kcal"] = round(out["kcal"])
    return out


def health_score(row: dict) -> dict:
    """Transparent 0-100 score computed from per-100 g values. Every component is returned."""
    comps: list[dict] = []

    def add(label: str, points: float, why: str) -> None:
        if abs(points) >= 0.05:
            comps.append({"label": label, "points": round(points, 1), "reason": why})

    add("Baseline", 60, "Every food starts at 60.")
    add("Fibre", min(row["fiber_g"] * 3, 15), f"+3 per g fibre per 100 g (max +15); this food has {row['fiber_g']} g.")
    add("Protein", min(row["protein_g"] * 0.5, 10), f"+0.5 per g protein per 100 g (max +10); {row['protein_g']} g.")
    add("Sugar", -min(row["sugar_g"] * 0.5, 15), f"-0.5 per g sugar per 100 g (max -15); {row['sugar_g']} g.")
    add("Saturated fat", -min(row["sat_fat_g"] * 1.5, 15), f"-1.5 per g saturated fat per 100 g (max -15); {row['sat_fat_g']} g.")
    add("Sodium", -min(row["sodium_mg"] / 40, 15), f"-1 per 40 mg sodium per 100 g (max -15); {row['sodium_mg']} mg.")
    if row["kcal"] > 250:
        add("Energy density", -min((row["kcal"] - 250) / 10, 15), "-1 per 10 kcal above 250 kcal per 100 g (max -15).")
    tags = set(row["tags"])
    if "whole" in tags or "lean_protein" in tags:
        add("Minimally processed", 10, "Whole-food or lean-protein item: +10.")
    if "fried" in tags:
        add("Fried", -8, "Deep-fried preparation: -8.")
    if "processed" in tags:
        add("Processed", -4, "Typically processed or refined: -4.")
    score = max(0, min(100, round(sum(c["points"] for c in comps))))
    grade = "Nutrient-dense choice" if score >= 75 else "Reasonable in moderation" if score >= 50 else "Best as an occasional food"
    return {
        "score": score, "grade": grade, "components": comps,
        "method": "Heuristic computed on per-100 g reference values; compares foods, not diets. Not medical advice.",
    }


def estimate(label: str | None = None, *, key: str | None = None, grams: float | None = None) -> dict:
    """Return a structured nutrition estimate for a food label or reference key."""
    key = key or (find_food(label) if label else None)
    if key is None or key not in _table():
        raise AppError(f"No nutrition reference found for '{label}'. Pick a food from the list instead.",
                       details={"label": label})
    row = _table()[key]
    if grams is not None and not (1 <= grams <= 3000):
        raise AppError("Portion must be between 1 g and 3000 g.")
    assumed = grams is None
    g = float(row["serving_g"] if assumed else grams)
    unc = PORTION_UNCERTAINTY_ASSUMED if assumed else PORTION_UNCERTAINTY_GIVEN
    per_serving = _scale(row, g)
    kcal = per_serving["kcal"]
    alts = [{"key": a, "name": _table()[a]["name"], "kcal_per_100g": _table()[a]["kcal"],
             "health_score": health_score(_table()[a])["score"]} for a in row["alternatives"] if a in _table()]
    return {
        "food_key": key, "food_name": row["name"], "category": row["category"],
        "portion": {"grams": g, "assumed": assumed, "description": row["serving_desc"] if assumed else f"{g:g} g (user provided)"},
        "nutrition": per_serving,
        "per_100g": _scale(row, 100.0),
        "uncertainty": {
            "relative": unc,
            "kcal_range": [round(kcal * (1 - unc)), round(kcal * (1 + unc))],
            "note": ("Serving size is an assumption; real portions vary a lot." if assumed
                     else "Based on the portion you entered; recipe and preparation still vary."),
        },
        "health": health_score(row),
        "healthier_alternatives": alts,
        "source": {"kind": "database", "dataset": DATASET_NAME},
        "disclaimer": DISCLAIMER,
    }
