import { Flame, ScanLine } from "lucide-react";
import { useState } from "react";
import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip as RTooltip } from "recharts";
import { Dropzone } from "../components/Dropzone";
import { SaveButton } from "../components/SaveButton";
import { Alert, Badge, Button, Card, Disclaimer, ErrorAlert, Field, PageHeader, ProgressBar, ResultSkeleton, SourceBadge, Tip } from "../components/ui";
import { useAsync, useQuery } from "../hooks/useAsync";
import { useLimits } from "../hooks/useLimits";
import { get, post, upload } from "../services/api";
import type { FoodAnalysis, NutritionEstimate } from "../types/api";
import { fmt, localDate } from "../utils/format";

const MACRO_COLORS = ["#059669", "#EFA21A", "#EC6F2A"];

export default function FoodScanner() {
  const limits = useLimits();
  const [files, setFiles] = useState<File[]>([]);
  const [grams, setGrams] = useState("");
  const [manual, setManual] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const result = useAsync<FoodAnalysis>();
  const foods = useQuery(() => get<{ key: string; name: string }[]>("/food/reference"), []);

  const gramsNum = grams.trim() === "" ? null : Number(grams);
  const gramsInvalid = gramsNum !== null && (!Number.isFinite(gramsNum) || gramsNum < 1 || gramsNum > 3000);

  async function analyze() {
    setFormError(null);
    if (!files[0]) return setFormError("Choose a food photo first.");
    if (gramsInvalid) return setFormError("Portion must be between 1 and 3000 grams.");
    const form = new FormData();
    form.append("file", files[0]);
    if (gramsNum !== null) form.append("grams", String(gramsNum));
    await result.run(() => upload<FoodAnalysis>("/food/analyze", form));
  }
  async function analyzeManual() {
    setFormError(null);
    if (!manual) return setFormError("Pick a food from the list.");
    if (gramsInvalid) return setFormError("Portion must be between 1 and 3000 grams.");
    await result.run(() => post<FoodAnalysis>("/food/manual", { label: manual, grams: gramsNum }));
  }

  const d = result.data;
  return (
    <>
      <PageHeader title="Food Scanner" icon={<ScanLine className="h-6 w-6" />}
        description="Upload a food photo to identify the dish and see estimated nutrition. Values come from a reference table and an assumed portion, so treat them as estimates." />
      <div className="grid gap-6 lg:grid-cols-[22rem_1fr]">
        <Card className="h-fit space-y-4">
          <Dropzone files={files} onChange={(f) => { setFiles(f); result.reset(); }} maxImageMb={limits.maxImageMb} label="Drop a food photo or click to browse" />
          <Field label="Portion in grams (optional)" htmlFor="grams" hint="Leave empty to use a typical serving. Entering your portion improves the estimate." tip="Calories scale with weight; a typical serving is only an assumption.">
            <input id="grams" className="input" inputMode="decimal" value={grams} onChange={(e) => setGrams(e.target.value)} placeholder="e.g. 250" aria-invalid={gramsInvalid} />
          </Field>
          {formError && <Alert tone="error">{formError}</Alert>}
          <Button className="w-full" loading={result.loading} onClick={analyze}>Analyse photo</Button>
          <details className="rounded-xl border border-stone-200 p-3 dark:border-white/10">
            <summary className="cursor-pointer text-sm font-medium">No model? Choose the food yourself</summary>
            <div className="mt-3 space-y-3">
              <select className="input" value={manual} onChange={(e) => setManual(e.target.value)} aria-label="Food">
                <option value="">Select a food...</option>
                {foods.data?.map((f) => <option key={f.key} value={f.key}>{f.name}</option>)}
              </select>
              <Button variant="ghost" className="w-full" loading={result.loading} onClick={analyzeManual}>Estimate nutrition</Button>
            </div>
          </details>
        </Card>

        <div className="space-y-5" aria-live="polite">
          <ErrorAlert error={result.error} />
          {result.loading && <Card><ResultSkeleton /></Card>}
          {!result.loading && !d && !result.error && (
            <Card><p className="py-10 text-center text-sm text-stone-500">Your analysis will appear here. Nothing is stored unless you choose to save it.</p></Card>
          )}
          {d && !result.loading && <Results data={d} />}
        </div>
      </div>
    </>
  );
}

function Results({ data }: { data: FoodAnalysis }) {
  const r = data.recognition;
  return (
    <>
      {r.status === "unavailable" && <Alert tone="info" title="No food-recognition model is configured">{r.message} The photo was validated but not identified; nothing was guessed.</Alert>}
      {r.status === "error" && <Alert tone="warn" title="Recognition failed">{r.message} You can still choose the food manually.</Alert>}
      {r.status === "no_food_detected" && <Alert tone="warn" title="No food detected">{r.message}</Alert>}
      {data.unmatched_labels.length > 0 && <Alert tone="info" title="Recognised but not in the nutrition table">{data.unmatched_labels.join(", ")}. No nutrition values were invented for these.</Alert>}
      {data.analyses.map((a) => <AnalysisCard key={a.food_key} a={a} />)}
      {data.notes.map((n) => <p key={n} className="text-xs text-stone-500 dark:text-slate-400">{n}</p>)}
    </>
  );
}

function AnalysisCard({ a }: { a: NutritionEstimate }) {
  const n = a.nutrition;
  const macroData = [
    { name: "Protein", value: Math.round(n.protein_g * 4) }, { name: "Carbs", value: Math.round(n.carbs_g * 4) }, { name: "Fat", value: Math.round(n.fat_g * 9) },
  ];
  const tone = a.health.score >= 75 ? "green" : a.health.score >= 50 ? "amber" : "orange";
  const src = a.prediction?.source;
  return (
    <Card className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-bold">{a.food_name}</h2>
          <div className="mt-2 flex flex-wrap gap-2">
            {a.prediction && <>
              <SourceBadge kind={src === "user_selected" ? "user" : "model"} />
              <Badge title={a.prediction.confidence_kind}>{a.prediction.confidence == null ? "Confidence: not provided" : `Confidence ${Math.round(a.prediction.confidence * 100)}% (uncalibrated)`}</Badge>
            </>}
            <SourceBadge kind="database" />
          </div>
        </div>
        <div className="text-right">
          <p className="flex items-center justify-end gap-1.5 font-display text-4xl font-bold"><Flame className="h-6 w-6 text-tangerine-500" />{fmt(n.kcal)}<span className="text-base font-medium text-stone-500"> kcal</span></p>
          <p className="text-xs text-stone-500 dark:text-slate-400">Likely range {a.uncertainty.kcal_range[0]}-{a.uncertainty.kcal_range[1]} kcal</p>
        </div>
      </div>

      <Alert tone="info" title={a.portion.assumed ? "Serving size is assumed" : "Using your portion"}>{a.portion.description} ({fmt(a.portion.grams)} g). {a.uncertainty.note}</Alert>

      <div className="grid gap-6 md:grid-cols-2">
        <div>
          <h3 className="mb-2 text-sm font-semibold">Macronutrients</h3>
          <div className="h-44" role="img" aria-label={`Calories from protein ${macroData[0].value}, carbs ${macroData[1].value}, fat ${macroData[2].value}`}>
            <ResponsiveContainer><PieChart>
              <Pie data={macroData} dataKey="value" innerRadius={42} outerRadius={70} paddingAngle={2}>{macroData.map((_, i) => <Cell key={i} fill={MACRO_COLORS[i]} />)}</Pie>
              <RTooltip formatter={(v: number) => `${v} kcal`} />
            </PieChart></ResponsiveContainer>
          </div>
          <div className="flex justify-center gap-4 text-xs">{macroData.map((m, i) => <span key={m.name} className="flex items-center gap-1"><i className="h-2.5 w-2.5 rounded-full" style={{ background: MACRO_COLORS[i] }} />{m.name}</span>)}</div>
        </div>
        <div className="space-y-3">
          <ProgressBar label="Protein" value={n.protein_g} max={50} sub={`${fmt(n.protein_g, 1)} g`} />
          <ProgressBar label="Carbohydrates" value={n.carbs_g} max={275} color="bg-saffron-500" sub={`${fmt(n.carbs_g, 1)} g`} />
          <ProgressBar label="Fat" value={n.fat_g} max={78} color="bg-tangerine-500" sub={`${fmt(n.fat_g, 1)} g`} />
          <ProgressBar label="Fibre" value={n.fiber_g ?? 0} max={28} color="bg-emerald-400" sub={`${fmt(n.fiber_g, 1)} g`} />
          <ProgressBar label="Sugar" value={n.sugar_g ?? 0} max={50} color="bg-amber-400" sub={`${fmt(n.sugar_g, 1)} g`} />
          <ProgressBar label="Sodium" value={n.sodium_mg ?? 0} max={2300} color="bg-sky-400" sub={`${fmt(n.sodium_mg)} mg`} />
          <p className="hint">Bars compare with common daily reference amounts (50 g protein, 275 g carbs, 78 g fat, 28 g fibre, 50 g sugar, 2,300 mg sodium).</p>
        </div>
      </div>

      <div>
        <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold">Health score <Tip text="A transparent heuristic over per-100 g reference values. It compares foods; it does not judge your whole diet." /></h3>
        <div className="flex items-center gap-4">
          <Badge tone={tone}>{a.health.score} / 100</Badge><span className="text-sm">{a.health.grade}</span>
        </div>
        <details className="mt-3 rounded-xl border border-stone-200 p-3 text-sm dark:border-white/10">
          <summary className="cursor-pointer font-medium">How this score was calculated</summary>
          <table className="mt-3 w-full text-left text-xs"><tbody>
            {a.health.components.map((c) => (
              <tr key={c.label} className="border-t border-stone-100 dark:border-white/10"><td className="py-1.5 pr-3 font-medium">{c.label}</td><td className={`pr-3 tabular-nums ${c.points < 0 ? "text-red-600" : "text-emerald-700 dark:text-emerald-400"}`}>{c.points > 0 ? "+" : ""}{c.points}</td><td className="text-stone-500 dark:text-slate-400">{c.reason}</td></tr>
            ))}
          </tbody></table>
          <p className="mt-2 text-xs text-stone-500">{a.health.method}</p>
        </details>
      </div>

      {a.healthier_alternatives.length > 0 && (
        <div><h3 className="mb-2 text-sm font-semibold">Healthier alternatives</h3>
          <ul className="flex flex-wrap gap-2">{a.healthier_alternatives.map((h) => <li key={h.key}><Badge tone="green">{h.name} - score {h.health_score}</Badge></li>)}</ul></div>
      )}

      <div className="flex flex-wrap items-start gap-3">
        <SaveButton kind="food_analysis" payload={a} />
        <LogButton a={a} />
      </div>
      <Disclaimer>{a.disclaimer} Dataset: {a.source.dataset}.</Disclaimer>
    </Card>
  );
}

function LogButton({ a }: { a: NutritionEstimate }) {
  const { run, loading, error } = useAsync<unknown>();
  const [done, setDone] = useState(false);
  return (
    <div className="space-y-2">
      <Button variant="ghost" loading={loading} disabled={done} onClick={async () => {
        const ok = await run(() => post("/meal-planner/log", { name: a.food_name, kcal: a.nutrition.kcal, protein_g: a.nutrition.protein_g, carbs_g: a.nutrition.carbs_g, fat_g: a.nutrition.fat_g, date: localDate() }));
        if (ok) setDone(true);
      }}>{done ? "Logged for today" : "Log to today's intake"}</Button>
      <ErrorAlert error={error} />
    </div>
  );
}
