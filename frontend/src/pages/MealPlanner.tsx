import { CalendarDays, Check } from "lucide-react";
import { useEffect, useState } from "react";
import { Alert, Badge, Button, Card, Disclaimer, EmptyState, ErrorAlert, Field, PageHeader, ProgressBar, ResultSkeleton, Skeleton } from "../components/ui";
import { useAsync, useQuery } from "../hooks/useAsync";
import { get, patch, post } from "../services/api";
import type { MealPlan, PlanMeal, Profile } from "../types/api";
import { fmt, localDate, qty, titleCase } from "../utils/format";

interface Options { allergens: string[]; diets: string[]; goals: string[]; activity_levels: string[]; age_ranges: string[]; cuisines: string[] }
type Saved = { id: string; created_at: string; plan: MealPlan } | null;
const blank: Profile = { age_range: "30-44", diet: "omnivore", food_preferences: [], allergies: [], avoid_foods: [], goal: "maintain", activity_level: "light", meals_per_day: 3, cuisine: null, max_prep_minutes: null, budget: null, calorie_target: null, consent_body_metrics: false, sex: null, age: null, height_cm: null, weight_kg: null };
const csv = (s: string) => s.split(",").map((x) => x.trim()).filter(Boolean);

export default function MealPlanner() {
  const [tab, setTab] = useState<"profile" | "plan" | "shopping">("profile");
  const [p, setP] = useState<Profile>(blank);
  const [allergyText, setAllergyText] = useState(""); const [avoidText, setAvoidText] = useState(""); const [likeText, setLikeText] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [saved, setSaved] = useState<Saved>(null);
  const [days, setDays] = useState<1 | 7>(7);
  const opts = useQuery(() => get<Options>("/meal-planner/options"), []);
  const existing = useQuery(() => get<Profile | null>("/meal-planner/profile"), []);
  const latest = useQuery(() => get<Saved>("/meal-planner"), []);
  const save = useAsync<{ targets: MealPlan["targets"]; recognised_allergens: string[]; free_text_allergens: string[]; disclaimer: string }>();
  const gen = useAsync<{ id: string; plan: MealPlan; created_at: string }>();

  useEffect(() => { const d = existing.data; if (d) { setP({ ...blank, ...d }); setAllergyText(d.allergies.join(", ")); setAvoidText(d.avoid_foods.join(", ")); setLikeText(d.food_preferences.join(", ")); } }, [existing.data]);
  useEffect(() => { if (latest.data) { setSaved(latest.data); setTab("plan"); } }, [latest.data]);

  const body = (): Profile => ({ ...p, allergies: csv(allergyText), avoid_foods: csv(avoidText), food_preferences: csv(likeText),
    ...(p.consent_body_metrics ? {} : { sex: null, age: null, height_cm: null, weight_kg: null }) });

  function validate(): string | null {
    const b = body();
    if (b.consent_body_metrics && (!b.sex || !b.age || !b.height_cm || !b.weight_kg)) return "Enter sex, age, height and weight, or turn off the body-measurement option.";
    if (b.age_range === "under_18" && ["lose_weight", "gain_weight", "build_muscle"].includes(b.goal)) return "Weight-change goals are not offered for under-18s.";
    return null;
  }
  async function saveProfile() {
    const v = validate(); setFormError(v); if (v) return;
    await save.run(() => post("/meal-planner/profile", body()));
  }
  async function generate() {
    const v = validate(); setFormError(v); if (v) return;
    const r = await gen.run(() => post<{ id: string; plan: MealPlan; created_at: string }>("/meal-planner/generate", { profile: body(), days }, 60_000));
    if (r) { setSaved({ id: r.id, created_at: r.created_at, plan: r.plan }); setTab("plan"); }
  }

  const tabs = [["profile", "Preferences"], ["plan", "Meal plan"], ["shopping", "Shopping list"]] as const;
  return (
    <>
      <PageHeader title="Meal Planner" icon={<CalendarDays className="h-6 w-6" />} description="Build a daily or weekly plan that respects your allergies and diet. Targets are general estimates, not medical advice." />
      <div role="tablist" className="mb-6 inline-flex rounded-xl border border-stone-200 bg-white p-1 dark:border-white/10 dark:bg-night-800">
        {tabs.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)} className={`rounded-lg px-4 py-2 text-sm font-medium ${tab === k ? "bg-emerald-600 text-white" : ""}`}>{l}</button>)}
      </div>
      <div className="space-y-5" aria-live="polite">
        <ErrorAlert error={gen.error} />
        {tab === "profile" && (existing.loading ? <Card><Skeleton className="h-64" /></Card> : (
          <Card className="space-y-5">
            <Alert tone="warn" title="Allergies are strict exclusions">Listed allergies and foods to avoid are always removed. If no safe plan exists we ask you to adjust rather than guess. Always check ingredient labels.</Alert>
            <div className="grid gap-4 md:grid-cols-3">
              <Field label="Age range" htmlFor="age"><select id="age" className="input" value={p.age_range} onChange={(e) => setP({ ...p, age_range: e.target.value })}>{(opts.data?.age_ranges ?? ["18-29"]).map((a) => <option key={a} value={a}>{titleCase(a)}</option>)}</select></Field>
              <Field label="Dietary pattern" htmlFor="diet"><select id="diet" className="input" value={p.diet} onChange={(e) => setP({ ...p, diet: e.target.value })}>{(opts.data?.diets ?? ["omnivore"]).map((a) => <option key={a} value={a}>{titleCase(a)}</option>)}</select></Field>
              <Field label="Goal" htmlFor="goal"><select id="goal" className="input" value={p.goal} onChange={(e) => setP({ ...p, goal: e.target.value })}>{(opts.data?.goals ?? ["maintain"]).map((a) => <option key={a} value={a}>{titleCase(a)}</option>)}</select></Field>
              <Field label="Allergies / intolerances" htmlFor="all" hint={`Known: ${(opts.data?.allergens ?? []).map(titleCase).join(", ")}`}><input id="all" className="input" value={allergyText} onChange={(e) => setAllergyText(e.target.value)} placeholder="dairy, peanuts" /></Field>
              <Field label="Foods to avoid" htmlFor="avoid"><input id="avoid" className="input" value={avoidText} onChange={(e) => setAvoidText(e.target.value)} placeholder="mushroom, tofu" /></Field>
              <Field label="Foods you like" htmlFor="like"><input id="like" className="input" value={likeText} onChange={(e) => setLikeText(e.target.value)} placeholder="lentils, rice" /></Field>
              <Field label="Meals per day" htmlFor="mpd"><select id="mpd" className="input" value={p.meals_per_day} onChange={(e) => setP({ ...p, meals_per_day: Number(e.target.value) })}>{[2, 3, 4, 5, 6].map((n) => <option key={n}>{n}</option>)}</select></Field>
              <Field label="Preferred cuisine" htmlFor="cui"><select id="cui" className="input" value={p.cuisine ?? ""} onChange={(e) => setP({ ...p, cuisine: e.target.value || null })}><option value="">No preference</option>{opts.data?.cuisines.map((c) => <option key={c} value={c}>{titleCase(c)}</option>)}</select></Field>
              <Field label="Max prep time (min)" htmlFor="prep"><input id="prep" className="input" inputMode="numeric" value={p.max_prep_minutes ?? ""} onChange={(e) => setP({ ...p, max_prep_minutes: e.target.value ? Number(e.target.value) : null })} placeholder="optional" /></Field>
              <Field label="Budget" htmlFor="bud"><select id="bud" className="input" value={p.budget ?? ""} onChange={(e) => setP({ ...p, budget: e.target.value || null })}><option value="">Not specified</option><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></Field>
              <Field label="Activity level" htmlFor="act"><select id="act" className="input" value={p.activity_level} onChange={(e) => setP({ ...p, activity_level: e.target.value })}>{(opts.data?.activity_levels ?? ["light"]).map((a) => <option key={a} value={a}>{titleCase(a)}</option>)}</select></Field>
              <Field label="Own calorie target (optional)" htmlFor="kcal" hint="Overrides the calculation."><input id="kcal" className="input" inputMode="numeric" value={p.calorie_target ?? ""} onChange={(e) => setP({ ...p, calorie_target: e.target.value ? Number(e.target.value) : null })} placeholder="1200-4000" /></Field>
            </div>
            <fieldset className="rounded-xl border border-stone-200 p-4 dark:border-white/10">
              <label className="flex cursor-pointer items-start gap-3 text-sm"><input type="checkbox" className="mt-1 h-4 w-4 accent-emerald-600" checked={p.consent_body_metrics} onChange={(e) => setP({ ...p, consent_body_metrics: e.target.checked })} />
                <span><b>Use my body measurements to estimate calories</b><br /><span className="text-stone-500 dark:text-slate-400">Optional. Adults only. Used for a Mifflin-St Jeor estimate; without it we use a general 2,000 kcal reference.</span></span></label>
              {p.consent_body_metrics && (
                <div className="mt-4 grid gap-4 sm:grid-cols-4">
                  <Field label="Sex" htmlFor="sex"><select id="sex" className="input" value={p.sex ?? ""} onChange={(e) => setP({ ...p, sex: e.target.value || null })}><option value="">Select</option><option value="female">Female</option><option value="male">Male</option></select></Field>
                  <Field label="Age" htmlFor="ageN"><input id="ageN" className="input" inputMode="numeric" value={p.age ?? ""} onChange={(e) => setP({ ...p, age: e.target.value ? Number(e.target.value) : null })} /></Field>
                  <Field label="Height (cm)" htmlFor="h"><input id="h" className="input" inputMode="decimal" value={p.height_cm ?? ""} onChange={(e) => setP({ ...p, height_cm: e.target.value ? Number(e.target.value) : null })} /></Field>
                  <Field label="Weight (kg)" htmlFor="w"><input id="w" className="input" inputMode="decimal" value={p.weight_kg ?? ""} onChange={(e) => setP({ ...p, weight_kg: e.target.value ? Number(e.target.value) : null })} /></Field>
                </div>)}
            </fieldset>
            {formError && <Alert tone="error">{formError}</Alert>}
            <ErrorAlert error={save.error} />
            {save.data && <Alert tone="success" title="Preferences saved">Daily target: <b>{save.data.targets.calories} kcal</b> ({save.data.targets.method}). {save.data.free_text_allergens.length > 0 && `Not in our allergen list, matched by ingredient name only: ${save.data.free_text_allergens.join(", ")}.`}</Alert>}
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="ghost" loading={save.loading} onClick={saveProfile}>Save preferences</Button>
              <div className="inline-flex rounded-xl border border-stone-200 p-1 dark:border-white/10">{([1, 7] as const).map((d) => <button key={d} type="button" onClick={() => setDays(d)} aria-pressed={days === d} className={`rounded-lg px-3 py-1.5 text-sm ${days === d ? "bg-emerald-100 font-semibold dark:bg-emerald-500/20" : ""}`}>{d === 1 ? "Daily" : "Weekly"}</button>)}</div>
              <Button loading={gen.loading} onClick={generate}>Generate plan</Button>
            </div>
          </Card>))}

        {tab === "plan" && (gen.loading ? <Card><ResultSkeleton /></Card> : saved
          ? <PlanView saved={saved} profile={body()} onChange={(plan) => setSaved({ ...saved, plan })} />
          : <EmptyState icon={<CalendarDays className="h-10 w-10" />} title="No meal plan yet" action={<Button onClick={() => setTab("profile")}>Set preferences</Button>}>Save your preferences and generate a plan to see it here.</EmptyState>)}
        {tab === "shopping" && (saved ? <Shopping saved={saved} onChange={(plan) => setSaved({ ...saved, plan })} /> : <EmptyState title="No shopping list yet">Generate a meal plan first.</EmptyState>)}
      </div>
    </>
  );
}

function PlanView({ saved, onChange }: { saved: NonNullable<Saved>; profile: Profile; onChange: (p: MealPlan) => void }) {
  const { plan } = saved;
  const [day, setDay] = useState(1);
  const d = plan.days.find((x) => x.day === day) ?? plan.days[0];
  const t = plan.targets;
  return (
    <div className="space-y-5">
      {plan.warnings.map((w) => <Alert key={w} tone="warn">{w}</Alert>)}
      {plan.notes.map((w) => <Alert key={w} tone="info">{w}</Alert>)}
      <Card className="space-y-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2"><h2 className="text-lg font-bold">Daily target: {t.calories} kcal</h2><span className="text-xs text-stone-500">{t.method}</span></div>
        <div className="grid gap-3 sm:grid-cols-4">
          <ProgressBar label="Calories" value={d.totals.kcal} max={t.calories} sub={`${fmt(d.totals.kcal)} / ${t.calories}`} />
          <ProgressBar label="Protein" value={d.totals.protein_g} max={t.macros_g.protein} color="bg-emerald-400" sub={`${fmt(d.totals.protein_g)} / ${t.macros_g.protein} g`} />
          <ProgressBar label="Carbs" value={d.totals.carbs_g} max={t.macros_g.carbs} color="bg-saffron-500" sub={`${fmt(d.totals.carbs_g)} / ${t.macros_g.carbs} g`} />
          <ProgressBar label="Fat" value={d.totals.fat_g} max={t.macros_g.fat} color="bg-tangerine-500" sub={`${fmt(d.totals.fat_g)} / ${t.macros_g.fat} g`} />
        </div>
        <details className="text-xs text-stone-600 dark:text-slate-400"><summary className="cursor-pointer font-medium">Assumptions</summary><ul className="mt-2 list-disc pl-5">{plan.assumptions.map((a) => <li key={a}>{a}</li>)}</ul></details>
      </Card>
      {plan.days.length > 1 && <div className="flex flex-wrap gap-2" role="tablist" aria-label="Days">{plan.days.map((x) => <button key={x.day} role="tab" aria-selected={x.day === day} onClick={() => setDay(x.day)} className={`rounded-xl border px-4 py-2 text-sm ${x.day === day ? "border-emerald-600 bg-emerald-600 text-white" : "border-stone-300 dark:border-white/15"}`}>Day {x.day}</button>)}</div>}
      {d.meals.map((m) => <MealCard key={m.slot} meal={m} planId={saved.id} day={d.day} onChange={onChange} />)}
      <Disclaimer>{plan.disclaimer}</Disclaimer>
    </div>
  );
}

function MealCard({ meal, planId, day, onChange }: { meal: PlanMeal; planId: string; day: number; onChange: (p: MealPlan) => void }) {
  const [alt, setAlt] = useState("");
  const rep = useAsync<{ plan: MealPlan }>();
  const log = useAsync<unknown>();
  const [logged, setLogged] = useState(false);
  async function replace(id?: string) {
    const r = await rep.run(() => post("/meal-planner/replace", { plan_id: planId, day, slot: meal.slot, meal_id: id || null }));
    if (r) onChange(r.plan);
  }
  return (
    <Card className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><Badge tone="green">{titleCase(meal.slot.replace(/_\d+$/, ""))}</Badge><h3 className="mt-1 text-xl font-bold">{meal.name}</h3>
          <p className="text-sm text-stone-500 dark:text-slate-400">{meal.servings} serving{meal.servings === 1 ? "" : "s"} - {meal.prep_minutes} min - {titleCase(meal.cuisine)}</p></div>
        <div className="text-right text-sm"><p className="font-display text-2xl font-bold">{meal.kcal} kcal</p><p className="text-xs text-stone-500">P {meal.protein_g} g - C {meal.carbs_g} g - F {meal.fat_g} g <span title="Estimates">(est.)</span></p></div>
      </div>
      {meal.allergens.length > 0 && <p className="text-xs text-stone-500">Contains: {meal.allergens.map(titleCase).join(", ")}</p>}
      <details className="text-sm"><summary className="cursor-pointer font-medium">Ingredients and method</summary>
        <div className="mt-2 grid gap-4 md:grid-cols-2"><ul className="space-y-1">{meal.ingredients.map((i, n) => <li key={n} className="flex justify-between border-b border-stone-100 py-1 dark:border-white/10"><span>{i.name}</span><span className="text-stone-500">{qty(i.quantity, i.unit)}</span></li>)}</ul>
          <ol className="list-decimal space-y-1 pl-5">{meal.steps.map((s) => <li key={s}>{s}</li>)}</ol></div></details>
      <ErrorAlert error={rep.error ?? log.error} />
      <div className="flex flex-wrap items-center gap-2">
        <Button variant="ghost" loading={rep.loading} onClick={() => replace()}>Swap for another</Button>
        {meal.alternatives.length > 0 && <>
          <select aria-label="Choose an alternative" className="input !w-auto" value={alt} onChange={(e) => setAlt(e.target.value)}><option value="">Alternatives...</option>{meal.alternatives.map((a) => <option key={a.meal_id} value={a.meal_id}>{a.name} ({a.kcal} kcal)</option>)}</select>
          <Button variant="soft" disabled={!alt} loading={rep.loading} onClick={() => replace(alt)}>Use</Button></>}
        <Button variant="soft" loading={log.loading} disabled={logged} onClick={async () => { if (await log.run(() => post("/meal-planner/log", { name: meal.name, kcal: meal.kcal, protein_g: meal.protein_g, carbs_g: meal.carbs_g, fat_g: meal.fat_g, date: localDate() }))) setLogged(true); }}>{logged ? <><Check className="h-4 w-4" /> Logged</> : "I ate this"}</Button>
      </div>
    </Card>
  );
}

function Shopping({ saved, onChange }: { saved: NonNullable<Saved>; onChange: (p: MealPlan) => void }) {
  const t = useAsync<{ shopping_list: MealPlan["shopping_list"] }>();
  const items = saved.plan.shopping_list;
  const bought = items.filter((i) => i.purchased).length;
  async function toggle(key: string, purchased: boolean) {
    const r = await t.run(() => patch<{ shopping_list: MealPlan["shopping_list"] }>("/meal-planner/shopping", { plan_id: saved.id, key, purchased }));
    if (r) onChange({ ...saved.plan, shopping_list: r.shopping_list });
  }
  return (
    <Card className="space-y-4">
      <div className="flex items-center justify-between"><h2 className="text-lg font-bold">Shopping list</h2><span className="text-sm text-stone-500">{bought} of {items.length} purchased</span></div>
      <ProgressBar label="Progress" value={bought} max={items.length} sub="" />
      <ErrorAlert error={t.error} />
      <ul className="grid gap-x-8 sm:grid-cols-2">{items.map((i) => (
        <li key={i.key} className="border-b border-stone-100 dark:border-white/10"><label className="flex cursor-pointer items-center gap-3 py-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-emerald-600" checked={i.purchased} onChange={(e) => toggle(i.key, e.target.checked)} />
          <span className={`flex-1 ${i.purchased ? "text-stone-400 line-through" : ""}`}>{i.name}</span><span className="tabular-nums text-stone-500">{qty(i.quantity, i.unit)}</span></label></li>
      ))}</ul>
    </Card>
  );
}
