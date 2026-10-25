export interface ApiEnvelope<T> { ok: boolean; data: T; meta?: Record<string, unknown> | null }
export interface ProviderStatus { configured: boolean; detail?: string | null }
export interface Health {
  status: "ok" | "degraded"; version: string; environment: string; database: boolean;
  providers: Record<string, ProviderStatus>; limits: { max_image_mb: number; max_video_mb: number; max_video_seconds: number };
}
export interface Macros { kcal: number; protein_g: number; carbs_g: number; fat_g: number; fiber_g?: number; sugar_g?: number; sat_fat_g?: number; sodium_mg?: number }
export interface HealthScore { score: number; grade: string; method: string; components: { label: string; points: number; reason: string }[] }
export interface NutritionEstimate {
  food_key: string; food_name: string; category: string;
  portion: { grams: number; assumed: boolean; description: string };
  nutrition: Macros; per_100g: Macros;
  uncertainty: { relative: number; kcal_range: [number, number]; note: string };
  health: HealthScore;
  healthier_alternatives: { key: string; name: string; kcal_per_100g: number; health_score: number }[];
  prediction?: { label: string; confidence: number | null; confidence_kind: string; source: string };
  source: { kind: string; dataset: string }; disclaimer: string;
}
export interface FoodAnalysis {
  recognition: { status: "ok" | "unavailable" | "error" | "no_food_detected"; source: string | null; message?: string | null; model?: string };
  analyses: NutritionEstimate[]; unmatched_labels: string[]; notes: string[];
}
export interface FreshnessResult {
  verdict: "no_visible_deterioration" | "signs_of_deterioration" | "uncertain"; verdict_label: string; category: string;
  confidence: { value: number; kind: string } | null;
  model: { name: string; kind: string; trained: boolean; label: string }; mode: string;
  evidence: { feature: string; value: number; level: string; observation: string }[];
  image_quality: { sharpness: number; brightness: number; warnings: string[] };
  warnings: string[]; reasons: string[]; recommendations: string[]; safety_notice: string;
}
export interface HygieneCriterion { label: string; weight: number; status: "pass" | "violation" | "not_assessed"; severity: string | null; observations: { frame: number; timestamp_s: number | null; severity: string; evidence: string }[] }
export interface HygieneReport {
  status: string; detector: string; detector_error?: string | null;
  score: { score: number | null; rating: string; coverage: number; message: string | null };
  criteria: Record<string, HygieneCriterion>;
  issues: { criterion: string; label: string; frame: number; timestamp_s: number | null; severity: string; evidence: string }[];
  corrective_actions: string[]; unobservable_criteria: string[]; notes: string[]; disclaimer: string; report_markdown: string;
  video: Record<string, unknown>; previews: FramePreview[];
}
export interface FramePreview { index: number; timestamp_s: number; jpeg_b64: string }
export interface Ingredient { name: string; quantity: number | null; unit: string }
export interface Recipe {
  id?: string | null; title: string; servings: number; prep_minutes: number; cook_minutes: number; difficulty: string;
  equipment?: string[]; ingredients: Ingredient[]; steps: string[]; safety_notes?: string[];
  substitutions?: { ingredient: string; substitute: string; for?: string }[]; waste_tips?: string[];
}
export interface RecipeResponse { source: "llm" | "local_fallback"; source_label: string; recipes: Recipe[]; fallback_reason: string | null; notes: string[]; disclaimer: string }
export interface PlanMeal {
  slot: string; meal_id: string; name: string; servings: number; kcal: number; protein_g: number; carbs_g: number; fat_g: number;
  prep_minutes: number; cuisine: string; allergens: string[]; ingredients: Ingredient[]; steps: string[]; alternatives: { meal_id: string; name: string; kcal: number }[];
}
export interface Targets { calories: number; method: string; macros_g: { protein: number; carbs: number; fat: number }; assumptions: string[]; bmr: number | null; tdee: number | null }
export interface MealPlan {
  days: { day: number; meals: PlanMeal[]; totals: Macros; calorie_gap: number }[]; targets: Targets; notes: string[]; warnings: string[]; assumptions: string[];
  shopping_list: { key: string; name: string; quantity: number; unit: string; purchased: boolean }[]; disclaimer: string;
}
export interface Profile {
  age_range: string; diet: string; food_preferences: string[]; allergies: string[]; avoid_foods: string[]; goal: string; activity_level: string;
  meals_per_day: number; cuisine: string | null; max_prep_minutes: number | null; budget: string | null; calorie_target: number | null;
  consent_body_metrics: boolean; sex: string | null; age: number | null; height_cm: number | null; weight_kg: number | null;
}
export interface HistoryRecord { id: string; kind: string; created_at: string; updated_at: string; payload: Record<string, any> }
export interface DashboardSummary {
  counts: Record<string, number>; today: (Macros & { date: string }) | null; targets: Targets | null; weekly: (Macros & { date: string })[];
  recent_analyses: { id: string; kind: string; title: string; created_at: string }[];
  alerts: { id: string; severity: string; source: string; message: string; created_at: string }[];
  meal_plan: { id: string; created_at: string; days: number; today_meals: string[] } | null; has_profile: boolean;
  recent_activity: { id: string; kind: string; created_at: string }[];
}
