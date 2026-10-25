import pytest

from app.database.repository import Repository
from app.services import dashboard
from app.services import meal_planner as mp


def test_empty_history_and_dashboard_have_no_fabricated_data():
    repo = Repository(":memory:")
    assert repo.list() == [] and repo.latest("meal_plan") is None and repo.get("nope") is None
    s = dashboard.summary(repo)
    assert s["recent_analyses"] == [] and s["alerts"] == [] and s["meal_plan"] is None and s["has_profile"] is False
    assert all(v == 0 for v in s["counts"].values()) and s["today"]["kcal"] == 0 and len(s["weekly"]) == 7


def test_crud_upsert_and_kind_validation():
    repo = Repository(":memory:")
    rec = repo.add("food_analysis", {"food_name": "Pizza"})
    assert rec["id"] and rec["created_at"] and repo.count("food_analysis") == 1
    repo.upsert("profile", "profile-default", {"diet": "vegan"})
    repo.upsert("profile", "profile-default", {"diet": "vegetarian"})
    assert repo.get("profile-default")["payload"]["diet"] == "vegetarian" and repo.count("profile") == 1
    assert repo.delete(rec["id"]) is True and repo.delete(rec["id"]) is False
    with pytest.raises(ValueError):
        repo.add("not_a_kind", {})
    with pytest.raises(ValueError):
        repo.list("not_a_kind")


def test_ordering_and_pagination():
    repo = Repository(":memory:")
    for i in range(5):
        repo.add("saved_recipe", {"title": f"r{i}"})
    titles = [r["payload"]["title"] for r in repo.list("saved_recipe", limit=2)]
    assert titles == ["r4", "r3"]
    assert [r["payload"]["title"] for r in repo.list("saved_recipe", limit=2, offset=4)] == ["r0"]


def test_dashboard_aggregates_alerts_and_intake():
    repo = Repository(":memory:")
    repo.add("freshness_analysis", {"verdict": "signs_of_deterioration", "category": "fruit", "verdict_label": "Signs of deterioration"})
    repo.add("hygiene_report", {"score": {"rating": "poor"}, "issues": [{"severity": "high", "label": "Hair covering"}]})
    repo.add("intake_log", {"kcal": 300, "protein_g": 10, "carbs_g": 40, "fat_g": 5})
    repo.add("intake_log", {"kcal": 200, "protein_g": 5, "carbs_g": 20, "fat_g": 5})
    plan = mp.generate_plan({"diet": "omnivore", "goal": "maintain", "meals_per_day": 3}, 1, seed=1)
    repo.add("meal_plan", plan)
    s = dashboard.summary(repo)
    assert s["today"]["kcal"] == 500 and s["targets"]["calories"] == 2000
    assert {a["source"] for a in s["alerts"]} == {"freshness", "hygiene"}
    assert s["meal_plan"]["today_meals"] and s["counts"]["meal_plan"] == 1
