"""Personalised meal planner.

Safety order of precedence (never relaxed):  allergens / avoid-list  >  diet pattern  >  everything else.
Soft constraints (budget, prep time) are relaxed with a visible note if they would leave a slot empty.
If a slot cannot be filled without breaking a hard rule the planner raises ClarificationNeeded.
All calories/macros are ESTIMATES from documented formulas and a built-in library, not medical advice.
"""
from __future__ import annotations

import copy
import random
import re
from functools import lru_cache

from app.data.meal_library import load_meals
from app.utils.errors import AppError, ClarificationNeeded, NotFound

DIETS = ["omnivore", "pescatarian", "vegetarian", "vegan"]
GOALS = ["maintain", "lose_weight", "gain_weight", "build_muscle", "eat_healthier"]
ACTIVITY = {"sedentary": 1.2, "light": 1.375, "moderate": 1.55, "active": 1.725}
GOAL_FACTOR = {"lose_weight": 0.85, "maintain": 1.0, "gain_weight": 1.10, "build_muscle": 1.08, "eat_healthier": 1.0}
MACRO_SPLIT = {  # share of calories: protein, carbs, fat
    "maintain": (0.20, 0.50, 0.30), "eat_healthier": (0.20, 0.50, 0.30), "lose_weight": (0.30, 0.40, 0.30),
    "gain_weight": (0.20, 0.50, 0.30), "build_muscle": (0.30, 0.45, 0.25),
}
KCAL_PER_G = {"protein": 4, "carbs": 4, "fat": 9}
DEFAULT_KCAL, MIN_KCAL, MAX_KCAL = 2000, 1200, 4000
AGE_RANGES = ["under_18", "18-29", "30-44", "45-59", "60+"]
SLOT_PLANS = {
    2: [("lunch", .50), ("dinner", .50)],
    3: [("breakfast", .27), ("lunch", .38), ("dinner", .35)],
    4: [("breakfast", .25), ("lunch", .33), ("dinner", .32), ("snack", .10)],
    5: [("breakfast", .22), ("snack", .09), ("lunch", .30), ("snack", .09), ("dinner", .30)],
    6: [("breakfast", .20), ("snack", .08), ("lunch", .27), ("snack", .08), ("dinner", .27), ("snack", .10)],
}
ALLERGENS = ["milk", "egg", "peanut", "tree_nut", "soy", "gluten", "fish", "shellfish", "sesame"]
ALLERGEN_ALIASES = {
    "dairy": ["milk"], "lactose": ["milk"], "milk": ["milk"], "eggs": ["egg"], "egg": ["egg"],
    "peanut": ["peanut"], "peanuts": ["peanut"], "tree nut": ["tree_nut"], "tree nuts": ["tree_nut"], "tree_nut": ["tree_nut"],
    "nuts": ["tree_nut", "peanut"], "nut": ["tree_nut", "peanut"], "soy": ["soy"], "soya": ["soy"],
    "gluten": ["gluten"], "wheat": ["gluten"], "celiac": ["gluten"], "coeliac": ["gluten"],
    "fish": ["fish"], "shellfish": ["shellfish"], "shrimp": ["shellfish"], "seafood": ["fish", "shellfish"],
    "sesame": ["sesame"],
}
ALLERGEN_KEYWORDS = {
    "milk": ["milk", "yogurt", "curd", "paneer", "cheese", "butter", "cream", "ghee", "whey"],
    "egg": ["egg", "mayonnaise", "mayo"],
    "peanut": ["peanut"],
    "tree_nut": ["almond", "walnut", "cashew", "pecan", "pistachio", "hazelnut", "macadamia"],
    "soy": ["soy", "tofu", "tempeh", "edamame", "miso"],
    "gluten": ["wheat", "flour", "bread", "toast", "pasta", "roti", "tortilla", "wrap", "noodle", "oats", "barley", "couscous", "spaghetti", "semolina", "rye"],
    "fish": ["salmon", "tuna", "fish", "anchovy", "cod"],
    "shellfish": ["shrimp", "prawn", "crab", "lobster", "mussel", "oyster"],
    "sesame": ["sesame", "tahini", "hummus"],
}
ANIMAL = {
    "vegan": ["chicken", "beef", "pork", "lamb", "fish", "salmon", "tuna", "shrimp", "prawn", "egg", "milk", "cheese", "butter", "yogurt", "paneer", "honey", "ghee", "mayonnaise", "curd"],
    "vegetarian": ["chicken", "beef", "pork", "lamb", "fish", "salmon", "tuna", "shrimp", "prawn", "gelatin"],
    "pescatarian": ["chicken", "beef", "pork", "lamb", "bacon", "ham"],
    "omnivore": [],
}
DISCLAIMER = ("Meal plans and calorie/macro targets are general estimates for healthy adults, not medical advice or a "
              "prescribed diet. Check ingredient labels for allergens. Talk to a doctor or registered dietitian for medical needs.")


# ---------------- helpers ----------------

@lru_cache
def library() -> tuple[dict, ...]:
    return tuple(load_meals())


_NUT_BUTTER = re.compile(r"\b(peanut|almond|cashew|nut|cocoa|shea) butter\b")


def _has_word(text: str, word: str) -> bool:
    # "peanut butter" is not dairy butter: rewrite to "peanut spread" (keeps the nut keyword intact)
    t = _NUT_BUTTER.sub(r"\1 spread", text.lower())
    return re.search(rf"\b{re.escape(word)}", t) is not None


def derived_allergens(meal: dict) -> set[str]:
    text = [i["name"] for i in meal["ingredients"]] + [meal["name"]]
    found = set()
    for allergen, words in ALLERGEN_KEYWORDS.items():
        if any(_has_word(t, w) for t in text for w in words):
            found.add(allergen)
    return found


def meal_allergens(meal: dict) -> set[str]:
    return set(meal["allergens"]) | derived_allergens(meal)


def normalize_allergies(items: list[str]) -> tuple[set[str], list[str]]:
    """-> (known allergen ids, free-text terms we could only substring-match)"""
    known, free = set(), []
    for raw in items:
        t = raw.strip().lower().replace("-", " ")
        if not t:
            continue
        if t in ALLERGEN_ALIASES:
            known.update(ALLERGEN_ALIASES[t])
        else:
            free.append(t)
    return known, free


def violations(meal: dict, profile: dict) -> list[str]:
    """Reasons this meal is NOT allowed for the profile (empty list = allowed)."""
    why = []
    known, free = normalize_allergies(profile.get("allergies", []))
    hit = meal_allergens(meal) & known
    if hit:
        why.append(f"contains allergen: {', '.join(sorted(hit))}")
    names = [i["name"] for i in meal["ingredients"]] + [meal["name"]]
    for term in free + [a.strip().lower() for a in profile.get("avoid_foods", []) if a.strip()]:
        if any(_has_word(n, term) or term in n.lower() for n in names):
            why.append(f"contains '{term}'")
    diet = profile.get("diet", "omnivore")
    if DIETS.index(meal["diet"]) < DIETS.index(diet):
        why.append(f"not {diet}")
    for w in ANIMAL.get(diet, []):
        if any(_has_word(i["name"], w) for i in meal["ingredients"]):
            why.append(f"{w} is not {diet}")
            break
    return why


# ---------------- targets ----------------

def compute_targets(profile: dict) -> dict:
    goal = profile.get("goal", "maintain")
    assumptions: list[str] = []
    under18 = profile.get("age_range") == "under_18"
    if under18 and goal in ("lose_weight", "gain_weight", "build_muscle"):
        raise ClarificationNeeded("Weight-change targets are not offered for under-18s. Choose 'maintain' or 'eat healthier', or speak to a paediatrician or dietitian.")
    bmr = tdee = None
    override = profile.get("calorie_target")
    if override:
        kcal, method = float(override), "User-provided calorie target"
        assumptions.append("You supplied your own daily calorie target; it is used as given.")
    elif profile.get("consent_body_metrics") and all(profile.get(k) for k in ("sex", "age", "height_cm", "weight_kg")) and not under18:
        w, h, a = profile["weight_kg"], profile["height_cm"], profile["age"]
        bmr = 10 * w + 6.25 * h - 5 * a + (5 if profile["sex"] == "male" else -161)
        tdee = bmr * ACTIVITY.get(profile.get("activity_level", "light"), 1.375)
        kcal = max(MIN_KCAL, min(MAX_KCAL, tdee * GOAL_FACTOR[goal]))
        method = "Mifflin-St Jeor equation x activity factor x goal adjustment"
        assumptions += [f"BMR {round(bmr)} kcal (Mifflin-St Jeor), activity x{ACTIVITY.get(profile.get('activity_level', 'light'), 1.375)}, "
                        f"goal adjustment x{GOAL_FACTOR[goal]}.", f"Result is limited to {MIN_KCAL}-{MAX_KCAL} kcal/day."]
    else:
        kcal, method = float(DEFAULT_KCAL), "General adult reference (2,000 kcal/day), not personalised"
        assumptions.append("No body measurements were used (not provided or consent not given), so the 2,000 kcal reference is applied.")
    p, c, f = MACRO_SPLIT[goal]
    kcal = round(kcal)
    return {
        "calories": kcal, "method": method, "bmr": round(bmr) if bmr else None, "tdee": round(tdee) if tdee else None,
        "macros_g": {"protein": round(kcal * p / 4), "carbs": round(kcal * c / 4), "fat": round(kcal * f / 9)},
        "macro_split_pct": {"protein": round(p * 100), "carbs": round(c * 100), "fat": round(f * 100)},
        "assumptions": assumptions + ["Macro split is a general guideline for the chosen goal and can be adjusted."],
    }


# ---------------- generation ----------------

def _round_q(x: float) -> float:
    return round(x * 4) / 4


def _scaled_meal(meal: dict, slot_kcal: float, alternatives: list[dict], slot_id: str) -> dict:
    factor = max(0.5, min(2.0, _round_q(slot_kcal / meal["kcal"]))) or 1.0
    ings = [{**i, "quantity": round(i["quantity"] * factor, 2)} for i in meal["ingredients"]]
    return {
        "slot": slot_id, "meal_id": meal["id"], "name": meal["name"], "servings": factor, "cuisine": meal["cuisine"],
        "diet": meal["diet"], "allergens": sorted(meal_allergens(meal)), "prep_minutes": meal["prep_minutes"],
        "kcal": round(meal["kcal"] * factor), "protein_g": round(meal["protein_g"] * factor, 1),
        "carbs_g": round(meal["carbs_g"] * factor, 1), "fat_g": round(meal["fat_g"] * factor, 1),
        "ingredients": ings, "steps": list(meal["steps"]),
        "alternatives": [{"meal_id": a["id"], "name": a["name"], "kcal": a["kcal"]} for a in alternatives],
    }


def _candidates(base_slot: str, profile: dict, notes: list[str]) -> list[dict]:
    hard = [m for m in library() if m["slot"] == base_slot and not violations(m, profile)]
    if not hard:
        raise ClarificationNeeded(
            f"No built-in {base_slot} option satisfies your allergies/avoid-list and diet. Please review them "
            f"(allergies: {', '.join(profile.get('allergies', [])) or 'none'}; avoid: {', '.join(profile.get('avoid_foods', [])) or 'none'}; "
            f"diet: {profile.get('diet', 'omnivore')}) or loosen an item. Safety exclusions are never ignored.",
            details={"slot": base_slot})
    soft = hard
    cap = {"low": 1, "medium": 2, "high": 3}.get(profile.get("budget") or "", 3)
    soft = [m for m in soft if m["cost"] <= cap]
    if profile.get("max_prep_minutes"):
        soft = [m for m in soft if m["prep_minutes"] <= profile["max_prep_minutes"]]
    if not soft:
        notes.append(f"No {base_slot} option fit your budget/prep-time limits, so those limits were relaxed for {base_slot}. Allergy and diet rules still apply.")
        return hard
    return soft


def _pick(cands: list[dict], profile: dict, rng: random.Random, recent: list[str], used: set[str]) -> dict:
    likes = [l.lower() for l in profile.get("food_preferences", [])]
    cuisine = (profile.get("cuisine") or "").lower()

    def score(m: dict) -> float:
        s = rng.random()
        if cuisine and m["cuisine"] == cuisine:
            s += 2
        if likes and any(l in (m["name"] + " " + " ".join(i["name"] for i in m["ingredients"])).lower() for l in likes):
            s += 1.5
        if m["id"] in recent:
            s -= 5
        if m["id"] in used:
            s -= 1
        return s
    return max(cands, key=score)


def shopping_list(plan_days: list[dict], previous: list[dict] | None = None) -> list[dict]:
    agg: dict[str, dict] = {}
    for d in plan_days:
        for m in d["meals"]:
            for i in m["ingredients"]:
                key = f"{i['name'].lower()}|{i['unit']}"
                row = agg.setdefault(key, {"key": key, "name": i["name"], "quantity": 0.0, "unit": i["unit"], "purchased": False})
                row["quantity"] = round(row["quantity"] + i["quantity"], 2)
    if previous:
        done = {p["key"] for p in previous if p.get("purchased")}
        for k in agg:
            agg[k]["purchased"] = k in done
    return sorted(agg.values(), key=lambda r: r["name"])


def day_totals(meals: list[dict]) -> dict:
    return {k: round(sum(m[k] for m in meals), 1) for k in ("kcal", "protein_g", "carbs_g", "fat_g")}


def verify_plan(plan: dict, profile: dict) -> None:
    """Final defence-in-depth pass: re-check every meal against hard exclusions."""
    lib = {m["id"]: m for m in library()}
    for d in plan["days"]:
        for m in d["meals"]:
            why = violations(lib[m["meal_id"]], profile)
            if why:
                raise ClarificationNeeded(f"Safety check failed for '{m['name']}' ({'; '.join(why)}). The plan was not returned.")


def generate_plan(profile: dict, days: int = 7, seed: int | None = None) -> dict:
    if days not in (1, 7):
        raise AppError("days must be 1 (daily plan) or 7 (weekly plan).")
    n = profile.get("meals_per_day", 3)
    if n not in SLOT_PLANS:
        raise AppError("meals_per_day must be between 2 and 6.")
    targets = compute_targets(profile)
    rng = random.Random(seed if seed is not None else 0)
    notes: list[str] = []
    known, free = normalize_allergies(profile.get("allergies", []))
    warnings = []
    if free:
        warnings.append("These allergy terms are not in the built-in allergen list and were only matched against ingredient names: "
                        + ", ".join(free) + ". Please double-check every recipe.")
    pools = {s: _candidates(s, profile, notes) for s in {s for s, _ in SLOT_PLANS[n]}}
    used: set[str] = set()
    history: list[list[str]] = []
    plan_days = []
    for d in range(1, days + 1):
        recent = [x for day in history[-2:] for x in day]
        day_ids: list[str] = []
        meals = []
        for idx, (slot, share) in enumerate(SLOT_PLANS[n]):
            cands = pools[slot]
            pick = _pick([c for c in cands if c["id"] not in day_ids] or cands, profile, rng, recent, used)
            alts = [c for c in cands if c["id"] != pick["id"] and c["id"] not in day_ids][:4]
            slot_id = slot if slot != "snack" else f"snack_{sum(1 for m in meals if m['slot'].startswith('snack')) + 1}"
            meals.append(_scaled_meal(pick, targets["calories"] * share, alts, slot_id))
            day_ids.append(pick["id"]); used.add(pick["id"])
        history.append(day_ids)
        tot = day_totals(meals)
        plan_days.append({"day": d, "meals": meals, "totals": tot, "calorie_gap": round(tot["kcal"] - targets["calories"])})
    plan = {"days": plan_days, "targets": targets, "notes": notes, "warnings": warnings, "disclaimer": DISCLAIMER,
            "assumptions": targets["assumptions"] + ["Portions are scaled in quarter-serving steps, so daily totals are close to, not exactly, the target."],
            "profile_summary": {k: profile.get(k) for k in ("diet", "allergies", "avoid_foods", "goal", "meals_per_day", "cuisine")},
            "shopping_list": []}
    verify_plan(plan, profile)
    plan["shopping_list"] = shopping_list(plan_days)
    return plan


def replace_meal(plan: dict, profile: dict, day: int, slot: str, meal_id: str | None = None, seed: int | None = None) -> dict:
    plan = copy.deepcopy(plan)
    d = next((x for x in plan["days"] if x["day"] == day), None)
    if d is None:
        raise NotFound(f"Day {day} is not in this plan.")
    idx = next((i for i, m in enumerate(d["meals"]) if m["slot"] == slot), None)
    if idx is None:
        raise NotFound(f"Slot '{slot}' is not in day {day}.")
    cur = d["meals"][idx]
    base_slot = slot.split("_")[0]
    lib = {m["id"]: m for m in library()}
    allowed = [m for m in library() if m["slot"] == base_slot and not violations(m, profile)]
    if meal_id:
        choice = next((m for m in allowed if m["id"] == meal_id), None)
        if choice is None:
            raise ClarificationNeeded("That meal is not available for your profile (it conflicts with an exclusion or is not a valid option for this slot).")
    else:
        others = [m for m in allowed if m["id"] not in {x["meal_id"] for x in d["meals"]}]
        if not others:
            raise ClarificationNeeded("No other safe option is available for this slot with your current exclusions.")
        choice = random.Random(seed).choice(others) if seed is not None else others[0]
    kcal_target = cur["kcal"]
    alts = [m for m in allowed if m["id"] != choice["id"]][:4]
    d["meals"][idx] = _scaled_meal(choice, kcal_target, alts, slot)
    d["totals"] = day_totals(d["meals"])
    d["calorie_gap"] = round(d["totals"]["kcal"] - plan["targets"]["calories"])
    verify_plan(plan, profile)
    plan["shopping_list"] = shopping_list(plan["days"], plan.get("shopping_list"))
    return plan
