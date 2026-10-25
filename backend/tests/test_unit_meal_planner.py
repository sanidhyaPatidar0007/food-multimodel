import itertools

import pytest

from app.services import meal_planner as mp
from app.utils.errors import AppError, ClarificationNeeded, NotFound

BASE = {"diet": "omnivore", "allergies": [], "avoid_foods": [], "food_preferences": [], "goal": "maintain", "meals_per_day": 3}
LIB = {m["id"]: m for m in mp.library()}


def prof(**kw):
    return {**BASE, **kw}


def test_library_declared_allergens_cover_ingredient_derived_allergens():
    for m in mp.library():
        assert mp.derived_allergens(m) <= set(m["allergens"]), m["id"]


def test_vegan_meals_contain_no_animal_ingredients():
    for m in mp.library():
        if m["diet"] == "vegan":
            assert not any(mp._has_word(i["name"], w) for i in m["ingredients"] for w in mp.ANIMAL["vegan"]), m["id"]


def test_nut_butter_is_not_dairy():
    pb = LIB["s-apple-pb"]
    assert "milk" not in mp.meal_allergens(pb) and "peanut" in mp.meal_allergens(pb)


def test_no_allergen_ever_appears_for_any_allergen_and_diet():
    for allergen, diet in itertools.product(mp.ALLERGENS, mp.DIETS):
        plan = mp.generate_plan(prof(allergies=[allergen], diet=diet, meals_per_day=5), 7, seed=11)
        for day in plan["days"]:
            for m in day["meals"]:
                assert allergen not in mp.meal_allergens(LIB[m["meal_id"]]), (allergen, diet, m["meal_id"])
                assert mp.DIETS.index(LIB[m["meal_id"]]["diet"]) >= mp.DIETS.index(diet)


def test_multiple_allergies_aliases_and_avoid_list():
    plan = mp.generate_plan(prof(allergies=["dairy", "nuts", "Wheat"], avoid_foods=["tofu", "mushroom"], diet="vegetarian"), 7, seed=2)
    for d in plan["days"]:
        for m in d["meals"]:
            meal = LIB[m["meal_id"]]
            assert not (mp.meal_allergens(meal) & {"milk", "tree_nut", "peanut", "gluten"})
            assert not any("tofu" in i["name"] for i in meal["ingredients"])


def test_free_text_allergen_is_matched_against_ingredients_and_warned():
    plan = mp.generate_plan(prof(allergies=["kidney beans"]), 7, seed=1)
    assert plan["warnings"] and "kidney beans" in plan["warnings"][0]
    assert all("kidney beans" not in i["name"] for d in plan["days"] for m in d["meals"] for i in m["ingredients"])


def test_impossible_constraints_ask_for_clarification_instead_of_violating():
    with pytest.raises(ClarificationNeeded):
        mp.generate_plan(prof(diet="vegan", allergies=["soy", "gluten", "tree nut", "peanut", "sesame"], avoid_foods=["chickpea", "lentil", "potato", "rice", "banana", "carrot", "apple", "oats", "fruit", "kidney", "makhana", "poha", "khichdi", "pasta", "dal"]), 7)


def test_verify_plan_rejects_a_tampered_plan():
    plan = mp.generate_plan(prof(allergies=["fish"]), 1, seed=5)
    plan["days"][0]["meals"][0]["meal_id"] = "d-salmon-sweetpotato"
    with pytest.raises(ClarificationNeeded):
        mp.verify_plan(plan, prof(allergies=["fish"]))


def test_soft_constraints_relax_with_note_but_hard_ones_never():
    plan = mp.generate_plan(prof(budget="low", max_prep_minutes=5, allergies=["peanut"]), 1, seed=1)
    assert plan["notes"]
    for m in plan["days"][0]["meals"]:
        assert "peanut" not in mp.meal_allergens(LIB[m["meal_id"]])


def test_targets_default_and_override_and_body_metrics():
    t = mp.compute_targets(prof())
    assert t["calories"] == 2000 and "not personalised" in t["method"]
    assert mp.compute_targets(prof(calorie_target=1800))["calories"] == 1800
    t = mp.compute_targets(prof(consent_body_metrics=True, sex="female", age=30, height_cm=165, weight_kg=60, activity_level="sedentary"))
    # BMR = 600 + 1031.25 - 150 - 161 = 1320.25 ; x1.2 = 1584.3
    assert t["bmr"] == 1320 and t["calories"] == 1584 and "Mifflin" in t["method"]
    t = mp.compute_targets(prof(consent_body_metrics=True, sex="female", age=30, height_cm=150, weight_kg=40, goal="lose_weight"))
    assert t["calories"] == 1200   # floor applies
    assert sum(t["macro_split_pct"].values()) == 100


def test_body_metrics_ignored_without_consent_and_under18_rules():
    t = mp.compute_targets(prof(sex="male", age=30, height_cm=180, weight_kg=80))
    assert t["calories"] == 2000
    with pytest.raises(ClarificationNeeded):
        mp.compute_targets(prof(age_range="under_18", goal="lose_weight"))


def test_plan_shape_totals_and_slots():
    for n, slots in ((2, 2), (3, 3), (4, 4), (5, 5), (6, 6)):
        plan = mp.generate_plan(prof(meals_per_day=n), 1, seed=1)
        d = plan["days"][0]
        assert len(d["meals"]) == slots
        assert abs(d["totals"]["kcal"] - sum(m["kcal"] for m in d["meals"])) < 1
        assert abs(d["calorie_gap"]) < 450 and all(m["alternatives"] is not None for m in d["meals"])
    with pytest.raises(AppError):
        mp.generate_plan(prof(meals_per_day=9), 1)
    with pytest.raises(AppError):
        mp.generate_plan(prof(), 3)


def test_weekly_plan_is_varied_and_deterministic_for_a_seed():
    a = mp.generate_plan(prof(), 7, seed=4)
    b = mp.generate_plan(prof(), 7, seed=4)
    assert [m["meal_id"] for d in a["days"] for m in d["meals"]] == [m["meal_id"] for d in b["days"] for m in d["meals"]]
    assert len({m["meal_id"] for d in a["days"] for m in d["meals"] if m["slot"] == "dinner"}) >= 4


def test_shopping_list_aggregates_and_preserves_purchased_state():
    plan = mp.generate_plan(prof(), 7, seed=1)
    keys = [i["key"] for i in plan["shopping_list"]]
    assert len(keys) == len(set(keys)) and all(not i["purchased"] for i in plan["shopping_list"])
    plan["shopping_list"][0]["purchased"] = True
    kept = plan["shopping_list"][0]["key"]
    new = mp.replace_meal(plan, prof(), 1, "dinner", None)
    assert next(i for i in new["shopping_list"] if i["key"] == kept)["purchased"] is True


def test_replace_meal_enforces_exclusions_and_validates_targets():
    p = prof(allergies=["fish", "shellfish"])
    plan = mp.generate_plan(p, 1, seed=1)
    new = mp.replace_meal(plan, p, 1, "dinner")
    assert new["days"][0]["meals"][2]["meal_id"] != plan["days"][0]["meals"][2]["meal_id"]
    with pytest.raises(ClarificationNeeded):
        mp.replace_meal(plan, p, 1, "dinner", "d-salmon-sweetpotato")
    with pytest.raises(NotFound):
        mp.replace_meal(plan, p, 5, "dinner")
    with pytest.raises(NotFound):
        mp.replace_meal(plan, p, 1, "snack_3")
