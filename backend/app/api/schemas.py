"""Pydantic request/response models (Pydantic v2)."""
from __future__ import annotations

import json
from datetime import date as _date
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

Diet = Literal["omnivore", "pescatarian", "vegetarian", "vegan"]
Restriction = Literal["gluten_free", "dairy_free", "egg_free", "nut_free", "soy_free"]
Goal = Literal["maintain", "lose_weight", "gain_weight", "build_muscle", "eat_healthier"]
Activity = Literal["sedentary", "light", "moderate", "active"]


class ApiResponse(BaseModel):
    ok: bool = True
    data: Any | None = None
    meta: dict[str, Any] | None = None


class ErrorBody(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = None


class ErrorResponse(BaseModel):
    ok: bool = False
    error: ErrorBody


class ProviderStatus(BaseModel):
    configured: bool
    detail: str | None = None


class HealthData(BaseModel):
    status: Literal["ok", "degraded"]
    version: str
    environment: str
    database: bool
    providers: dict[str, ProviderStatus]
    limits: dict[str, float]


def _clean_list(values: list[str], max_items: int, max_len: int) -> list[str]:
    out = []
    for v in values:
        v = v.strip()
        if v and v.lower() not in {o.lower() for o in out}:
            if len(v) > max_len:
                raise ValueError(f"Items must be at most {max_len} characters.")
            out.append(v)
    if len(out) > max_items:
        raise ValueError(f"At most {max_items} items are allowed.")
    return out


class FoodManualRequest(BaseModel):
    label: str = Field(min_length=1, max_length=80)
    grams: float | None = Field(default=None, ge=1, le=3000)


class RecipeRequest(BaseModel):
    ingredients: list[str] = Field(default_factory=list)
    equipment: list[str] = Field(default_factory=list)
    diet: Diet = "omnivore"
    restrictions: list[Restriction] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)
    dish: str | None = Field(default=None, max_length=120)
    servings: int | None = Field(default=None, ge=1, le=50)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("ingredients", "equipment", "avoid")
    @classmethod
    def _lists(cls, v: list[str]) -> list[str]:
        return _clean_list(v, 40, 60)

    @model_validator(mode="after")
    def _need_something(self) -> "RecipeRequest":
        if not (self.ingredients or self.dish):
            raise ValueError("Provide at least one ingredient or a desired dish.")
        return self


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=2000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=30)
    recipe: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _last_is_user(self) -> "ChatRequest":
        if self.messages[-1].role != "user":
            raise ValueError("The last message must come from the user.")
        return self


class ScaleRequest(BaseModel):
    recipe: dict[str, Any]
    servings: int = Field(ge=1, le=50)


class ProfileIn(BaseModel):
    age_range: Literal["under_18", "18-29", "30-44", "45-59", "60+"]
    diet: Diet = "omnivore"
    food_preferences: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    avoid_foods: list[str] = Field(default_factory=list)
    goal: Goal = "maintain"
    activity_level: Activity = "light"
    meals_per_day: int = Field(default=3, ge=2, le=6)
    cuisine: str | None = Field(default=None, max_length=40)
    max_prep_minutes: int | None = Field(default=None, ge=5, le=240)
    budget: Literal["low", "medium", "high"] | None = None
    calorie_target: int | None = Field(default=None, ge=1200, le=4000)
    consent_body_metrics: bool = False
    sex: Literal["female", "male"] | None = None
    age: int | None = Field(default=None, ge=18, le=100)
    height_cm: float | None = Field(default=None, ge=120, le=230)
    weight_kg: float | None = Field(default=None, ge=30, le=250)

    @field_validator("food_preferences", "allergies", "avoid_foods")
    @classmethod
    def _lists(cls, v: list[str]) -> list[str]:
        return _clean_list(v, 25, 40)

    @model_validator(mode="after")
    def _consent_rules(self) -> "ProfileIn":
        metrics = [self.sex, self.age, self.height_cm, self.weight_kg]
        if self.consent_body_metrics:
            if self.age_range == "under_18":
                raise ValueError("Body-measurement calculations are only available for adults (18+).")
            if any(m is None for m in metrics):
                raise ValueError("sex, age, height_cm and weight_kg are required when consent_body_metrics is true.")
        elif any(m is not None for m in metrics):
            raise ValueError("Body measurements were provided without consent_body_metrics=true; they were not accepted.")
        return self


class GeneratePlanRequest(BaseModel):
    profile: ProfileIn | None = None
    days: Literal[1, 7] = 7
    seed: int | None = Field(default=None, ge=0, le=1_000_000)


class ReplaceMealRequest(BaseModel):
    plan_id: str
    day: int = Field(ge=1, le=7)
    slot: str = Field(min_length=3, max_length=20)
    meal_id: str | None = Field(default=None, max_length=60)


class ShoppingToggle(BaseModel):
    plan_id: str
    key: str = Field(min_length=1, max_length=120)
    purchased: bool


class IntakeLog(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kcal: float = Field(ge=0, le=5000)
    protein_g: float = Field(default=0, ge=0, le=500)
    carbs_g: float = Field(default=0, ge=0, le=1000)
    fat_g: float = Field(default=0, ge=0, le=500)
    date: _date | None = None


class HistoryCreate(BaseModel):
    kind: Literal["food_analysis", "freshness_analysis", "hygiene_report", "saved_recipe"]
    payload: dict[str, Any]

    @field_validator("payload")
    @classmethod
    def _size(cls, v: dict[str, Any]) -> dict[str, Any]:
        if len(json.dumps(v)) > 250_000:
            raise ValueError("Payload is too large.")
        return v
