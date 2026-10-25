import { Leaf } from "lucide-react";
import { useState } from "react";
import { Dropzone } from "../components/Dropzone";
import { SaveButton } from "../components/SaveButton";
import { Alert, Badge, Button, Card, Disclaimer, ErrorAlert, Field, PageHeader, ResultSkeleton, SourceBadge } from "../components/ui";
import { useAsync, useQuery } from "../hooks/useAsync";
import { useLimits } from "../hooks/useLimits";
import { get, upload } from "../services/api";
import type { FreshnessResult } from "../types/api";
import { titleCase } from "../utils/format";

const VERDICT_TONE = { no_visible_deterioration: "green", signs_of_deterioration: "red", uncertain: "amber" } as const;

export default function Freshness() {
  const limits = useLimits();
  const [files, setFiles] = useState<File[]>([]);
  const [category, setCategory] = useState("fruit");
  const [formError, setFormError] = useState<string | null>(null);
  const cats = useQuery(() => get<string[]>("/freshness/categories"), []);
  const result = useAsync<FreshnessResult>();

  async function analyze() {
    if (!files[0]) return setFormError("Choose a photo first.");
    setFormError(null);
    const form = new FormData();
    form.append("file", files[0]); form.append("category", category);
    await result.run(() => upload<FreshnessResult>("/freshness/analyze", form));
  }
  const d = result.data;

  return (
    <>
      <PageHeader title="Freshness Check" icon={<Leaf className="h-6 w-6" />}
        description="A visual check for discolouration, dark spots and mould-like patches. It cannot tell whether food is microbiologically safe." />
      <Alert tone="warn" title="A photo cannot prove food is safe">Never rely on appearance alone. Follow use-by dates and storage rules, and discard food when in doubt.</Alert>
      <div className="mt-6 grid gap-6 lg:grid-cols-[22rem_1fr]">
        <Card className="h-fit space-y-4">
          <Dropzone files={files} onChange={(f) => { setFiles(f); result.reset(); }} maxImageMb={limits.maxImageMb} label="Drop a photo of the food" />
          <Field label="Food category" htmlFor="cat" hint="Meat, fish, dairy and cooked leftovers never get a positive visual verdict." tip="Different foods spoil differently; this changes which cues are applied.">
            <select id="cat" className="input" value={category} onChange={(e) => setCategory(e.target.value)}>
              {(cats.data ?? ["fruit", "vegetable", "other"]).map((c) => <option key={c} value={c}>{titleCase(c)}</option>)}
            </select>
          </Field>
          {formError && <Alert tone="error">{formError}</Alert>}
          <Button className="w-full" loading={result.loading} onClick={analyze}>Check freshness</Button>
          <p className="hint">Tip: use bright, even light and fill the frame with the food.</p>
        </Card>

        <div className="space-y-5" aria-live="polite">
          <ErrorAlert error={result.error} />
          {result.loading && <Card><ResultSkeleton /></Card>}
          {!d && !result.loading && !result.error && <Card><p className="py-10 text-center text-sm text-stone-500">Results appear here.</p></Card>}
          {d && !result.loading && (
            <Card className="space-y-5">
              <div className="flex flex-wrap items-center gap-3">
                <h2 className="text-2xl font-bold">{d.verdict_label}</h2>
                <Badge tone={VERDICT_TONE[d.verdict]}>{titleCase(d.category)}</Badge>
              </div>
              <div className="flex flex-wrap gap-2">
                <SourceBadge kind={d.model.trained ? "model" : "heuristic"} />
                <Badge title={d.confidence?.kind}>{d.confidence ? `Confidence ${Math.round(d.confidence.value * 100)}% (uncalibrated)` : "Confidence: not available"}</Badge>
              </div>
              {d.model.kind === "llm_vision" && <Alert tone="info" title="AI visual opinion">{d.model.label}. It judges only what is visible and never says food is safe.</Alert>}
              {!d.model.trained && <Alert tone="info" title="Demo baseline">{d.model.label}. Add a trained classifier (see the README) for model-based results.</Alert>}
              {d.warnings.length > 0 && <Alert tone="warn" title="This image limits reliability">
                <ul className="list-disc pl-4">{d.warnings.map((w) => <li key={w}>{w}</li>)}</ul></Alert>}
              {d.reasons.map((r) => <Alert key={r} tone="info">{r}</Alert>)}

              <div>
                <h3 className="mb-2 text-sm font-semibold">What the analysis saw</h3>
                <ul className="divide-y divide-stone-100 rounded-xl border border-stone-200 text-sm dark:divide-white/10 dark:border-white/10">
                  {d.evidence.map((e, i) => (
                    <li key={`${e.feature}-${i}`} className="flex items-start justify-between gap-3 px-3 py-2">
                      <div><p className="font-medium">{titleCase(e.feature)}</p><p className="text-xs text-stone-500 dark:text-slate-400">{e.observation}</p></div>
                      <Badge tone={e.level === "strong" ? "red" : e.level === "mild" ? "amber" : "neutral"}>{e.level === "model" ? `${Math.round(e.value * 100)}%` : e.level === "observed" ? "No concern" : e.level === "strong" || e.level === "mild" ? (e.value ? `${e.level} - ${(e.value * 100).toFixed(1)}%` : e.level) : `${e.level} - ${(e.value * 100).toFixed(1)}%`}</Badge>
                    </li>
                  ))}
                </ul>
              </div>

              <div><h3 className="mb-2 text-sm font-semibold">What to do</h3>
                <ul className="list-disc space-y-1 pl-5 text-sm">{d.recommendations.map((r) => <li key={r}>{r}</li>)}</ul></div>
              <SaveButton kind="freshness_analysis" payload={d} />
              <Disclaimer>{d.safety_notice}</Disclaimer>
            </Card>
          )}
        </div>
      </div>
    </>
  );
}
