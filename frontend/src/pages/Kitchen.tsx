import { ChefHat, Clock, Minus, Plus, Send, Users } from "lucide-react";
import { useRef, useState } from "react";
import { SaveButton } from "../components/SaveButton";
import { Alert, Badge, Button, Card, Disclaimer, EmptyState, ErrorAlert, Field, PageHeader, ResultSkeleton, SourceBadge } from "../components/ui";
import { useAsync } from "../hooks/useAsync";
import { post, upload } from "../services/api";
import type { Recipe, RecipeResponse } from "../types/api";
import { qty, titleCase } from "../utils/format";

const DIETS = ["omnivore", "pescatarian", "vegetarian", "vegan"];
const RESTRICTIONS = ["gluten_free", "dairy_free", "egg_free", "nut_free", "soy_free"];
const list = (s: string) => s.split(/[,\n]/).map((x) => x.trim()).filter(Boolean);

export default function Kitchen() {
  const [f, setF] = useState({ ingredients: "", equipment: "", diet: "omnivore", avoid: "", dish: "", servings: "2", notes: "" });
  const [restr, setRestr] = useState<string[]>([]);
  const [formError, setFormError] = useState<string | null>(null);
  const [recipes, setRecipes] = useState<RecipeResponse | null>(null);
  const gen = useAsync<RecipeResponse>();
  const scan = useAsync<{ ingredients: string[] }>();
  const photo = useRef<HTMLInputElement>(null);
  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => setF({ ...f, [k]: e.target.value });

  async function generate() {
    const servings = Number(f.servings);
    if (!list(f.ingredients).length && !f.dish.trim()) return setFormError("Add at least one ingredient or name a dish.");
    if (!Number.isInteger(servings) || servings < 1 || servings > 50) return setFormError("Servings must be a whole number from 1 to 50.");
    setFormError(null);
    const r = await gen.run(() => post<RecipeResponse>("/kitchen/recipe", {
      ingredients: list(f.ingredients), equipment: list(f.equipment), diet: f.diet, restrictions: restr, avoid: list(f.avoid),
      dish: f.dish.trim() || null, servings, notes: f.notes.trim() || null,
    }, 90_000));
    if (r) setRecipes(r);
  }
  async function scanPhotos(files: FileList | null) {
    if (!files?.length) return;
    const form = new FormData();
    Array.from(files).slice(0, 4).forEach((x) => form.append("files", x));
    const r = await scan.run(() => upload<{ ingredients: string[] }>("/kitchen/ingredients/scan", form, 90_000));
    if (r) setF((p) => ({ ...p, ingredients: [...new Set([...list(p.ingredients), ...r.ingredients])].join(", ") }));
  }

  return (
    <>
      <PageHeader title="Smart Kitchen" icon={<ChefHat className="h-6 w-6" />} description="Turn the ingredients you have into recipes, adjust servings, tick off steps and ask follow-up questions." />
      <div className="grid gap-6 lg:grid-cols-[24rem_1fr]">
        <Card className="h-fit space-y-4">
          <Field label="Ingredients you have" htmlFor="ing" hint="Separate with commas."><textarea id="ing" rows={3} className="input" value={f.ingredients} onChange={set("ingredients")} placeholder="rice, broccoli, garlic, eggs" /></Field>
          <div>
            <input ref={photo} type="file" hidden multiple accept="image/jpeg,image/png,image/webp" onChange={(e) => { scanPhotos(e.target.files); e.target.value = ""; }} />
            <Button variant="ghost" className="w-full" loading={scan.loading} onClick={() => photo.current?.click()}>Add ingredients from photos</Button>
            {scan.error && <div className="mt-2"><ErrorAlert error={scan.error} /></div>}
          </div>
          <Field label="Dish you want (optional)" htmlFor="dish"><input id="dish" className="input" value={f.dish} onChange={set("dish")} placeholder="e.g. vegetable curry" /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Diet" htmlFor="diet"><select id="diet" className="input" value={f.diet} onChange={set("diet")}>{DIETS.map((d) => <option key={d} value={d}>{titleCase(d)}</option>)}</select></Field>
            <Field label="Servings" htmlFor="serv"><input id="serv" className="input" inputMode="numeric" value={f.servings} onChange={set("servings")} /></Field>
          </div>
          <fieldset><legend className="label">Restrictions</legend>
            <div className="flex flex-wrap gap-2">{RESTRICTIONS.map((r) => (
              <label key={r} className={`cursor-pointer rounded-full border px-3 py-1 text-xs ${restr.includes(r) ? "border-emerald-600 bg-emerald-50 text-emerald-800 dark:bg-emerald-500/10 dark:text-emerald-300" : "border-stone-300 dark:border-white/15"}`}>
                <input type="checkbox" className="sr-only" checked={restr.includes(r)} onChange={() => setRestr(restr.includes(r) ? restr.filter((x) => x !== r) : [...restr, r])} />{titleCase(r)}</label>
            ))}</div></fieldset>
          <Field label="Foods to avoid" htmlFor="avoid" hint="Allergies take priority; these are never used."><input id="avoid" className="input" value={f.avoid} onChange={set("avoid")} placeholder="peanuts, mushrooms" /></Field>
          <Field label="Equipment" htmlFor="eq"><input id="eq" className="input" value={f.equipment} onChange={set("equipment")} placeholder="oven, one pot" /></Field>
          <Field label="Notes" htmlFor="notes"><input id="notes" className="input" value={f.notes} onChange={set("notes")} placeholder="quick, kid-friendly" maxLength={500} /></Field>
          {formError && <Alert tone="error">{formError}</Alert>}
          <Button className="w-full" loading={gen.loading} onClick={generate}>Find recipes</Button>
        </Card>

        <div className="space-y-5" aria-live="polite">
          <ErrorAlert error={gen.error} onRetry={generate} />
          {gen.loading && <Card><ResultSkeleton /></Card>}
          {!recipes && !gen.loading && <EmptyState icon={<ChefHat className="h-10 w-10" />} title="No recipes yet">Tell the kitchen what you have and what you can eat.</EmptyState>}
          {recipes && !gen.loading && <>
            <div className="flex flex-wrap items-center gap-2"><SourceBadge kind={recipes.source === "llm" ? "llm" : "fallback"} /><span className="text-sm text-stone-600 dark:text-slate-400">{recipes.source_label}</span></div>
            {recipes.fallback_reason && <Alert tone="info" title="Using built-in example recipes">{recipes.fallback_reason}</Alert>}
            {recipes.notes.map((n) => <Alert key={n} tone="warn">{n}</Alert>)}
            {recipes.recipes.map((r, i) => <RecipeCard key={`${r.title}-${i}`} recipe={r} />)}
            <Disclaimer>{recipes.disclaimer}</Disclaimer>
          </>}
          <Chat recipe={recipes?.recipes[0] ?? null} />
        </div>
      </div>
    </>
  );
}

function RecipeCard({ recipe: initial }: { recipe: Recipe }) {
  const [recipe, setRecipe] = useState(initial);
  const [done, setDone] = useState<Set<number>>(new Set());
  const scale = useAsync<Recipe>();
  async function setServings(n: number) {
    if (n < 1 || n > 50) return;
    const r = await scale.run(() => post<Recipe>("/kitchen/scale", { recipe, servings: n }));
    if (r) setRecipe({ ...recipe, ...r });
  }
  return (
    <Card className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div><h2 className="text-2xl font-bold">{recipe.title}</h2>
          <div className="mt-2 flex flex-wrap gap-2 text-xs"><Badge tone="green"><Clock className="h-3 w-3" /> Prep {recipe.prep_minutes} min</Badge><Badge tone="orange">Cook {recipe.cook_minutes} min</Badge><Badge>{titleCase(recipe.difficulty)}</Badge></div></div>
        <div className="flex items-center gap-2 rounded-xl border border-stone-200 p-1 dark:border-white/10" role="group" aria-label="Servings">
          <Button variant="ghost" className="!px-2.5 !py-1.5" aria-label="Fewer servings" disabled={scale.loading || recipe.servings <= 1} onClick={() => setServings(recipe.servings - 1)}><Minus className="h-4 w-4" /></Button>
          <span className="flex min-w-[5.5rem] items-center justify-center gap-1.5 text-sm font-semibold"><Users className="h-4 w-4" />{recipe.servings} servings</span>
          <Button variant="ghost" className="!px-2.5 !py-1.5" aria-label="More servings" disabled={scale.loading || recipe.servings >= 50} onClick={() => setServings(recipe.servings + 1)}><Plus className="h-4 w-4" /></Button>
        </div>
      </div>
      <ErrorAlert error={scale.error} />
      <div className="grid gap-6 md:grid-cols-[1fr_1.4fr]">
        <div><h3 className="mb-2 text-sm font-semibold">Ingredients</h3>
          <ul className="space-y-1 text-sm">{recipe.ingredients.map((i, n) => <li key={n} className="flex justify-between gap-3 border-b border-stone-100 py-1 dark:border-white/10"><span>{i.name}</span><span className="tabular-nums text-stone-500">{qty(i.quantity, i.unit)}</span></li>)}</ul></div>
        <div><h3 className="mb-2 text-sm font-semibold">Steps <span className="font-normal text-stone-500">({done.size}/{recipe.steps.length} done)</span></h3>
          <ol className="space-y-2">{recipe.steps.map((s, n) => (
            <li key={n}><label className="flex cursor-pointer items-start gap-3 text-sm"><input type="checkbox" className="mt-1 h-4 w-4 accent-emerald-600" checked={done.has(n)} onChange={() => { const d = new Set(done); d.has(n) ? d.delete(n) : d.add(n); setDone(d); }} />
              <span className={done.has(n) ? "text-stone-400 line-through" : ""}><b className="mr-1">{n + 1}.</b>{s}</span></label></li>
          ))}</ol></div>
      </div>
      {!!recipe.safety_notes?.length && <Alert tone="warn" title="Food safety"><ul className="list-disc pl-4">{recipe.safety_notes.map((s) => <li key={s}>{s}</li>)}</ul></Alert>}
      {!!recipe.substitutions?.length && <div><h3 className="mb-2 text-sm font-semibold">Substitutions</h3><ul className="list-disc space-y-1 pl-5 text-sm">{recipe.substitutions.map((s, n) => <li key={n}><b>{s.ingredient}</b>{s.for ? ` (${s.for})` : ""}: {s.substitute}</li>)}</ul></div>}
      {!!recipe.waste_tips?.length && <div><h3 className="mb-2 text-sm font-semibold">Reduce food waste</h3><ul className="list-disc space-y-1 pl-5 text-sm">{recipe.waste_tips.map((s) => <li key={s}>{s}</li>)}</ul></div>}
      <SaveButton kind="saved_recipe" payload={recipe} label="Save recipe" />
    </Card>
  );
}

function Chat({ recipe }: { recipe: Recipe | null }) {
  const [msgs, setMsgs] = useState<{ role: "user" | "assistant"; content: string; source?: string }[]>([]);
  const [text, setText] = useState("");
  const chat = useAsync<{ source: string; reply: string }>();
  async function send() {
    const t = text.trim();
    if (!t) return;
    const next = [...msgs, { role: "user" as const, content: t }];
    setMsgs(next); setText("");
    const r = await chat.run(() => post("/kitchen/chat", { messages: next.map(({ role, content }) => ({ role, content })), recipe }, 60_000));
    if (r) setMsgs([...next, { role: "assistant", content: r.reply, source: r.source }]);
  }
  return (
    <Card className="space-y-3">
      <h2 className="text-lg font-bold">Ask the kitchen</h2>
      <div className="max-h-80 space-y-3 overflow-y-auto" role="log" aria-live="polite">
        {msgs.length === 0 && <p className="text-sm text-stone-500">Ask about temperatures, substitutions, storage or timing.</p>}
        {msgs.map((m, i) => (
          <div key={i} className={`max-w-[85%] rounded-2xl px-3.5 py-2 text-sm ${m.role === "user" ? "ml-auto bg-emerald-600 text-white" : "bg-stone-100 dark:bg-white/10"}`}>
            {m.content}{m.source === "local_fallback" && <span className="mt-1 block text-[11px] opacity-70">Local fallback answer, not an AI model</span>}
          </div>
        ))}
        {chat.loading && <p className="text-sm text-stone-500">Thinking...</p>}
      </div>
      <ErrorAlert error={chat.error} />
      <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); send(); }}>
        <input className="input" aria-label="Your question" value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. What temperature is chicken done?" maxLength={2000} />
        <Button type="submit" aria-label="Send" disabled={!text.trim()} loading={chat.loading}><Send className="h-4 w-4" /></Button>
      </form>
    </Card>
  );
}
