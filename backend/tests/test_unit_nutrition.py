import pytest

from app.services import nutrition as n
from app.utils.errors import AppError


def test_lookup_exact_alias_and_fuzzy():
    assert n.find_food("pizza") == "pizza"
    assert n.find_food("Grilled chicken breast") == "grilled_chicken"
    assert n.find_food("fries") == "french_fries"
    assert n.find_food("strawbery") == "strawberry"


def test_unknown_food_returns_none_and_estimate_raises():
    assert n.find_food("zzzz qqqq") is None
    assert n.find_food("") is None
    with pytest.raises(AppError):
        n.estimate("zzzz qqqq")


def test_estimate_scales_with_grams_and_is_labelled_database():
    a = n.estimate("rice", grams=100)
    b = n.estimate("rice", grams=200)
    assert b["nutrition"]["kcal"] == a["nutrition"]["kcal"] * 2
    assert a["source"]["kind"] == "database"
    assert "estimate" in a["disclaimer"].lower()


def test_assumed_portion_has_wider_uncertainty_than_user_portion():
    assumed = n.estimate("pizza")
    given = n.estimate("pizza", grams=assumed["portion"]["grams"])
    assert assumed["portion"]["assumed"] and not given["portion"]["assumed"]
    lo_a, hi_a = assumed["uncertainty"]["kcal_range"]
    lo_g, hi_g = given["uncertainty"]["kcal_range"]
    assert (hi_a - lo_a) > (hi_g - lo_g)
    assert lo_a < assumed["nutrition"]["kcal"] < hi_a


def test_portion_bounds():
    for bad in (0, -5, 5000):
        with pytest.raises(AppError):
            n.estimate("apple", grams=bad)


def test_health_score_bounds_and_ordering():
    scores = {k: n.estimate(key=k)["health"]["score"] for k in ("broccoli", "salmon", "pizza", "donut", "french_fries")}
    assert all(0 <= s <= 100 for s in scores.values())
    assert scores["broccoli"] > scores["pizza"] > scores["donut"]
    comps = n.estimate(key="donut")["health"]["components"]
    assert comps[0]["label"] == "Baseline" and all({"label", "points", "reason"} <= set(c) for c in comps)


def test_every_reference_food_estimates_cleanly():
    for f in n.list_foods():
        r = n.estimate(key=f["key"])
        assert r["nutrition"]["kcal"] >= 0 and 0 <= r["health"]["score"] <= 100
        for alt in r["healthier_alternatives"]:
            assert alt["key"] in {x["key"] for x in n.list_foods()}


def test_descriptive_extra_words_do_not_borrow_another_foods_nutrition():
    assert n.find_food("beet salad") is None          # not the generic "mixed green salad"
    assert n.find_food("peanut butter sandwich") is None
    assert n.find_food("grilled chicken breast slice") == "grilled_chicken"
    assert n.find_food("macaroni and cheese") == "mac_and_cheese"
    assert n.find_food("apple pie") == "apple_pie"


def test_food101_style_labels_map_when_in_table():
    for label, key in (("french_fries", "french_fries"), ("donuts", "donut"), ("chicken_wings", "chicken_wings"), ("hot_dog", "hot_dog")):
        assert n.find_food(label.replace("_", " ")) == key
