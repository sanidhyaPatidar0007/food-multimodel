"""Aggregates stored records into the dashboard summary. Nothing here is fabricated: empty data => empty sections."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from app.database.repository import Repository


def _day(iso: str) -> str:
    return iso[:10]


def summary(repo: Repository, today_date: date | None = None) -> dict:
    """`today_date` is the *client's* local date, so users far from the server's timezone see the right day."""
    today_date = today_date or date.today()
    today = today_date.isoformat()
    logs = repo.list("intake_log", limit=500)
    week_days = [(today_date - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    totals = {d: {"date": d, "kcal": 0.0, "protein_g": 0.0, "carbs_g": 0.0, "fat_g": 0.0} for d in week_days}
    for rec in logs:
        d = rec["payload"].get("date") or _day(rec["created_at"])
        if d in totals:
            for k in ("kcal", "protein_g", "carbs_g", "fat_g"):
                totals[d][k] += float(rec["payload"].get(k, 0) or 0)
    weekly = [{**v, **{k: round(v[k], 1) for k in ("kcal", "protein_g", "carbs_g", "fat_g")}} for v in totals.values()]
    plan = repo.latest("meal_plan")
    profile = repo.get("profile-default")
    targets = plan["payload"]["targets"] if plan else None

    recent = []
    for kind in ("food_analysis", "freshness_analysis", "hygiene_report", "saved_recipe"):
        for r in repo.list(kind, limit=5):
            p = r["payload"]
            title = (p.get("title") or p.get("food_name") or p.get("verdict_label") or
                     (f"Hygiene review ({p['score']['rating']})" if p.get("score") else kind.replace("_", " ")))
            recent.append({"id": r["id"], "kind": kind, "title": title, "created_at": r["created_at"]})
    recent.sort(key=lambda r: r["created_at"], reverse=True)

    alerts = []
    for r in repo.list("freshness_analysis", limit=20):
        if r["payload"].get("verdict") == "signs_of_deterioration":
            alerts.append({"id": r["id"], "severity": "high", "source": "freshness", "message": f"Signs of deterioration noted in a {r['payload'].get('category', 'food')} item.", "created_at": r["created_at"]})
    for r in repo.list("hygiene_report", limit=20):
        issues = [i for i in r["payload"].get("issues", []) if i.get("severity") in ("high", "medium")]
        if issues:
            alerts.append({"id": r["id"], "severity": issues[0]["severity"], "source": "hygiene", "message": f"{len(issues)} hygiene issue(s) flagged: {issues[0]['label']}.", "created_at": r["created_at"]})
    alerts.sort(key=lambda a: a["created_at"], reverse=True)

    return {
        "counts": {k: repo.count(k) for k in ("food_analysis", "freshness_analysis", "hygiene_report", "saved_recipe", "meal_plan")},
        "today": next((w for w in weekly if w["date"] == today), None),
        "targets": targets, "weekly": weekly, "recent_analyses": recent[:8], "alerts": alerts[:6],
        "meal_plan": ({"id": plan["id"], "created_at": plan["created_at"], "days": len(plan["payload"]["days"]),
                       "today_meals": [m["name"] for m in plan["payload"]["days"][0]["meals"]]} if plan else None),
        "has_profile": profile is not None,
        "recent_activity": [{"id": r["id"], "kind": r["kind"], "created_at": r["created_at"]} for r in repo.list(None, limit=8)],
    }
