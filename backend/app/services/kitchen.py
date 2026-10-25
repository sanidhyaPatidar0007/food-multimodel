"""Smart Kitchen: LLM recipe generation + chat with a clearly labelled local fallback."""
from __future__ import annotations

import copy
import logging
import re

from app.data.fallback_recipes import RECIPES, SUBSTITUTIONS
from app.services.llm import LLM, extract_json, has_vision
from app.utils.errors import AppError, ProviderError, ProviderUnavailable

log = logging.getLogger("foodverse.kitchen")

DIETS = ["omnivore", "pescatarian", "vegetarian", "vegan"]
EXTRA_RESTRICTIONS = ["gluten_free", "dairy_free", "egg_free", "nut_free", "soy_free"]
ANIMAL_WORDS = {
    "vegan": ["chicken", "beef", "pork", "lamb", "fish", "salmon", "tuna", "shrimp", "prawn", "egg", "milk", "cheese", "butter", "yogurt", "honey", "cream", "bacon", "ham", "gelatin"],
    "vegetarian": ["chicken", "beef", "pork", "lamb", "fish", "salmon", "tuna", "shrimp", "prawn", "bacon", "ham", "gelatin"],
    "pescatarian": ["chicken", "beef", "pork", "lamb", "bacon", "ham"],
}
RESTRICTION_WORDS = {
    "gluten_free": ["wheat", "flour", "pasta", "spaghetti", "bread", "noodle", "couscous", "barley", "soy sauce"],
    "dairy_free": ["milk", "cheese", "butter", "yogurt", "cream"],
    "egg_free": ["egg", "mayonnaise"],
    "nut_free": ["almond", "walnut", "cashew", "pecan", "pistachio", "hazelnut", "peanut", "nut"],
    "soy_free": ["soy", "tofu", "tempeh", "edamame"],
}
DISCLAIMER = "Check recipes against your own allergies and cook food to safe temperatures. This is general guidance, not medical advice."


def _contains(name: str, words: list[str]) -> str | None:
    n = name.lower()
    for w in words:
        if re.search(rf"\b{re.escape(w)}", n):
            return w
    return None


def find_violations(recipe: dict, diet: str, restrictions: list[str], avoid: list[str]) -> list[str]:
    """Ingredient names that break the diet, restrictions or user avoid-list."""
    bad = []
    for ing in recipe["ingredients"]:
        name = ing["name"]
        for w in ANIMAL_WORDS.get(diet, []):
            if _contains(name, [w]):
                bad.append(f"{name} (not {diet})")
        for r in restrictions:
            if _contains(name, RESTRICTION_WORDS.get(r, [])):
                bad.append(f"{name} ({r.replace('_', ' ')})")
        for a in avoid:
            if a.strip() and a.strip().lower() in name.lower():
                bad.append(f"{name} (you avoid '{a.strip()}')")
    return sorted(set(bad))


def scale_recipe(recipe: dict, servings: int) -> dict:
    if not 1 <= servings <= 50:
        raise AppError("Servings must be between 1 and 50.")
    r = copy.deepcopy(recipe)
    factor = servings / max(1, recipe["servings"])
    for ing in r["ingredients"]:
        q = ing.get("quantity")
        if isinstance(q, (int, float)):
            v = q * factor
            ing["quantity"] = round(v, 2) if v < 10 else round(v)
    r["servings"] = servings
    return r


def waste_tips(ingredients: list[str]) -> list[str]:
    text = " ".join(i.lower() for i in ingredients)
    tips = []
    if any(w in text for w in ("broccoli", "carrot", "onion", "celery")):
        tips.append("Save vegetable peels and stalks in the freezer to make stock.")
    if any(w in text for w in ("parsley", "cilantro", "coriander", "basil", "herb")):
        tips.append("Blend leftover herbs with oil and freeze in an ice-cube tray.")
    if "bread" in text:
        tips.append("Turn stale bread into breadcrumbs or croutons.")
    if "rice" in text:
        tips.append("Cool leftover rice within an hour, refrigerate, and use within a day.")
    tips.append("Cook the most perishable ingredients first and store the rest according to their labels.")
    return tips


def substitutions_for(ingredients: list[str], diet: str, restrictions: list[str]) -> list[dict]:
    wanted = {diet, *restrictions}
    out = []
    for ing in ingredients:
        key = next((k for k in SUBSTITUTIONS if _contains(ing, [k])), None)
        if key:
            for need in wanted:
                if need in SUBSTITUTIONS[key]:
                    out.append({"ingredient": ing, "for": need.replace("_", " "), "substitute": SUBSTITUTIONS[key][need]})
    return out


def _fallback_to_recipe(r: dict) -> dict:
    return {"id": r["id"], "title": r["title"], "servings": r["servings"], "prep_minutes": r["prep_minutes"],
            "cook_minutes": r["cook_minutes"], "difficulty": r["difficulty"], "equipment": r["equipment"],
            "ingredients": [{"name": n, "quantity": q, "unit": u} for n, q, u in r["ingredients"]],
            "steps": list(r["steps"]), "safety_notes": list(r["safety"]), "diet": r["diet"]}


def fallback_recipes(ingredients: list[str], diet: str, restrictions: list[str], avoid: list[str], servings: int | None) -> list[dict]:
    have = " ".join(i.lower() for i in ingredients)
    scored = []
    for raw in RECIPES:
        rec = _fallback_to_recipe(raw)
        # DIETS is ordered least -> most restrictive; a recipe is usable if it is at least as restrictive as the user's diet.
        if DIETS.index(raw["diet"]) < DIETS.index(diet):
            continue
        if find_violations(rec, diet, restrictions, avoid):
            continue
        hits = sum(1 for ing in rec["ingredients"] if any(tok in have for tok in ing["name"].lower().split() if len(tok) > 3))
        scored.append((hits, rec))
    scored.sort(key=lambda t: -t[0])
    out = []
    for hits, rec in scored[:3]:
        rec = scale_recipe(rec, servings) if servings else rec
        rec["matched_ingredients"] = hits
        out.append(rec)
    return out


RECIPE_SYSTEM = (
    "You are a careful home-cooking assistant. Return JSON only: "
    '{"recipes":[{"title":str,"servings":int,"prep_minutes":int,"cook_minutes":int,"difficulty":"easy|medium|hard",'
    '"equipment":[str],"ingredients":[{"name":str,"quantity":number,"unit":str}],"steps":[str],'
    '"safety_notes":[str],"substitutions":[{"ingredient":str,"substitute":str}],"waste_tips":[str]}]}. '
    "Return 1-2 recipes. Strictly respect the diet, restrictions and avoid-list: never include a forbidden ingredient. "
    "Give numeric quantities, safe internal temperatures where relevant, and numbered-step instructions as plain strings."
)


def normalize_recipe(raw: dict) -> dict:
    """Validate/coerce an LLM recipe; raise ProviderError if essential fields are missing."""
    try:
        ings = [{"name": str(i["name"]), "quantity": float(i["quantity"]) if i.get("quantity") is not None else None,
                 "unit": str(i.get("unit", ""))} for i in raw["ingredients"]]
        steps = [str(s) for s in raw["steps"]]
        if not ings or not steps:
            raise ValueError
        return {"id": None, "title": str(raw["title"])[:120], "servings": max(1, int(raw.get("servings", 2))),
                "prep_minutes": max(0, int(raw.get("prep_minutes", 0))), "cook_minutes": max(0, int(raw.get("cook_minutes", 0))),
                "difficulty": raw.get("difficulty") if raw.get("difficulty") in ("easy", "medium", "hard") else "medium",
                "equipment": [str(e) for e in raw.get("equipment", [])], "ingredients": ings, "steps": steps,
                "safety_notes": [str(s) for s in raw.get("safety_notes", [])],
                "substitutions": [s for s in raw.get("substitutions", []) if isinstance(s, dict)],
                "waste_tips": [str(s) for s in raw.get("waste_tips", [])]}
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise ProviderError("The AI model returned a recipe in an unexpected format.") from exc


class KitchenService:
    def __init__(self, llm: LLM):
        self.llm = llm

    async def recipes(self, *, ingredients: list[str], equipment: list[str], diet: str, restrictions: list[str],
                      avoid: list[str], dish: str | None, servings: int | None, notes: str | None,
                      images_b64: list[str] | None = None) -> dict:
        reason = None
        if self.llm.available:
            prompt = (f"Ingredients available: {', '.join(ingredients) or 'not specified'}\nEquipment: {', '.join(equipment) or 'standard kitchen'}\n"
                      f"Diet: {diet}\nRestrictions: {', '.join(restrictions) or 'none'}\nMust avoid: {', '.join(avoid) or 'none'}\n"
                      f"Desired dish: {dish or 'your suggestion'}\nServings: {servings or 2}\nNotes: {notes or 'none'}")
            try:
                data = extract_json(await self.llm.complete(RECIPE_SYSTEM, [{"role": "user", "content": prompt}], images_b64=images_b64, max_tokens=5000))
                if isinstance(data, list):  # some models return the bare list of recipes
                    data = {"recipes": data}
                if not isinstance(data, dict):
                    raise ProviderError("The AI model returned an unexpected structure.")
                recs = [normalize_recipe(r) for r in (data.get("recipes") or [])]
                safe, rejected = [], []
                for r in recs:
                    v = find_violations(r, diet, restrictions, avoid)
                    (rejected if v else safe).append((r, v))
                if safe:
                    out = []
                    for r, _ in safe:
                        r["waste_tips"] = r["waste_tips"] or waste_tips([i["name"] for i in r["ingredients"]])
                        out.append(scale_recipe(r, servings) if servings else r)
                    return self._resp("llm", out, None, [f"Discarded a generated recipe: {', '.join(v)}" for _, v in rejected])
                reason = "The AI recipe broke your dietary rules and was discarded." if rejected else "The AI returned no recipes."
            except (ProviderUnavailable, ProviderError) as exc:
                reason = exc.message
                log.warning("LLM recipe generation failed: %s", reason)
        else:
            reason = "No LLM is configured (set LLM_PROVIDER and LLM_API_KEY)."
        local = fallback_recipes(ingredients, diet, restrictions, avoid, servings)
        for r in local:
            r["waste_tips"] = waste_tips([i["name"] for i in r["ingredients"]])
            r["substitutions"] = substitutions_for([i["name"] for i in r["ingredients"]], diet, restrictions)
        return self._resp("local_fallback", local, reason, [] if local else ["No built-in recipe matches your diet and restrictions."])

    @staticmethod
    def _resp(source: str, recipes: list[dict], fallback_reason: str | None, notes: list[str]) -> dict:
        return {"source": source, "recipes": recipes, "fallback_reason": fallback_reason, "notes": notes,
                "source_label": "Generated by an AI model" if source == "llm" else
                "Built-in example recipes (local fallback) - NOT generated by an AI model",
                "disclaimer": DISCLAIMER}

    async def chat(self, messages: list[dict], recipe: dict | None) -> dict:
        if self.llm.available:
            system = ("You are FoodVerse's cooking assistant. Be concise and practical. Give safe cooking temperatures and "
                      "storage advice conservatively; never give medical advice. If the user mentions an allergy, respect it strictly.")
            if recipe:
                system += f"\nCurrent recipe context: {recipe.get('title')} - ingredients: {', '.join(i['name'] for i in recipe.get('ingredients', []))}."
            try:
                text = await self.llm.complete(system, messages[-12:], max_tokens=2000)
                return {"source": "llm", "reply": text.strip(), "fallback_reason": None}
            except (ProviderUnavailable, ProviderError) as exc:
                return {"source": "local_fallback", "reply": self._rule_reply(messages[-1]["content"], recipe), "fallback_reason": exc.message}
        return {"source": "local_fallback", "reply": self._rule_reply(messages[-1]["content"], recipe),
                "fallback_reason": "No LLM is configured."}

    @staticmethod
    def _rule_reply(q: str, recipe: dict | None) -> str:
        t = q.lower()
        pre = "(Local fallback - simple built-in answers, not an AI model.) "
        if any(w in t for w in ("temperature", "done", "cooked through", "safe to eat")):
            return pre + "Safe minimum internal temperatures: poultry and leftovers 74 C / 165 F; ground meat 71 C / 160 F; whole cuts of beef, pork and lamb 63 C / 145 F; fish 63 C / 145 F. Use a food thermometer in the thickest part."
        if any(w in t for w in ("substitute", "replace", "instead of", "swap")):
            hits = [f"{k}: " + "; ".join(v.values()) for k, v in SUBSTITUTIONS.items() if k in t]
            return pre + ("Possible swaps - " + " | ".join(hits) if hits else "Tell me the ingredient and the restriction (e.g. vegan, gluten free) and I'll check my small substitution list.")
        if any(w in t for w in ("waste", "leftover", "store", "storage", "keep")):
            return pre + "Refrigerate cooked food within 2 hours, store in shallow covered containers, and eat leftovers within 3-4 days. " + waste_tips([])[-1]
        if recipe:
            return pre + f"I can't answer open-ended questions without an AI model configured. For '{recipe.get('title')}', try asking about temperatures, substitutions or storage."
        return pre + "I can answer basic questions about safe temperatures, substitutions and storage. Configure an LLM for open-ended help."


    async def scan_ingredients(self, images_b64: list[str]) -> dict:
        """Identify visible ingredients in photos. Requires a vision-capable LLM (no local fallback exists)."""
        system = ('Identify the food ingredients clearly visible in the photo(s). Respond with JSON only: '
                  '{"ingredients":["name",...]}. Do not guess items that are hidden or unclear.')
        raw = await self.llm.complete(system, [{"role": "user", "content": "What ingredients do you see?"}], images_b64=images_b64, max_tokens=1500)
        data = extract_json(raw)
        if isinstance(data, list):
            data = {"ingredients": data}
        if not isinstance(data, dict):
            raise ProviderError("The AI model returned an unexpected structure.")
        names = [str(n).strip()[:60] for n in (data.get("ingredients") or []) if str(n).strip()]
        return {"source": "llm_vision", "ingredients": names[:30]}
