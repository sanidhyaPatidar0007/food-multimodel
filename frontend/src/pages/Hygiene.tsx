import { Download, ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import { Dropzone } from "../components/Dropzone";
import { SaveButton } from "../components/SaveButton";
import { Alert, Badge, Button, Card, Disclaimer, EmptyState, ErrorAlert, Field, PageHeader, ResultSkeleton, Tip } from "../components/ui";
import { useAsync, useQuery } from "../hooks/useAsync";
import { useLimits } from "../hooks/useLimits";
import { get, upload } from "../services/api";
import type { FramePreview, HygieneReport } from "../types/api";
import { download, titleCase } from "../utils/format";

interface Criteria { criteria: Record<string, { label: string; weight: number }>; unobservable: string[]; defaults: { min_coverage: number; band_good: number; band_attention: number } }
const SEV = { high: "red", medium: "orange", low: "amber" } as const;

export default function Hygiene() {
  const limits = useLimits();
  const [files, setFiles] = useState<File[]>([]);
  const [interval, setInterval_] = useState("2");
  const [maxFrames, setMaxFrames] = useState("12");
  const [weights, setWeights] = useState<Record<string, number>>({});
  const [minCov, setMinCov] = useState(0.4);
  const [formError, setFormError] = useState<string | null>(null);
  const crit = useQuery(() => get<Criteria>("/hygiene/criteria"), []);
  const frames = useAsync<{ frames: FramePreview[] }>();
  const report = useAsync<HygieneReport>();

  useEffect(() => {
    if (crit.data) { setWeights(Object.fromEntries(Object.entries(crit.data.criteria).map(([k, v]) => [k, v.weight]))); setMinCov(crit.data.defaults.min_coverage); }
  }, [crit.data]);

  function build(): FormData | null {
    const i = Number(interval), m = Number(maxFrames);
    if (!files.length) { setFormError("Upload a short video or one or more images."); return null; }
    if (!(i >= 0.1 && i <= 60)) { setFormError("Frame interval must be between 0.1 and 60 seconds."); return null; }
    if (!(Number.isInteger(m) && m >= 1 && m <= 120)) { setFormError("Maximum frames must be a whole number from 1 to 120."); return null; }
    setFormError(null);
    const f = new FormData();
    files.forEach((x) => f.append("files", x));
    f.append("interval_seconds", String(i)); f.append("max_frames", String(m));
    return f;
  }

  async function preview() { const f = build(); if (f) await frames.run(() => upload("/hygiene/frames", f, 180_000)); }
  async function analyze() {
    const f = build(); if (!f) return;
    f.append("config", JSON.stringify({ weights, min_coverage: minCov }));
    await report.run(() => upload<HygieneReport>("/hygiene/analyze", f, 240_000));
  }
  const r = report.data;

  return (
    <>
      <PageHeader title="Hygiene Monitor" icon={<ShieldCheck className="h-6 w-6" />}
        description="Screen a short kitchen video or photos for visible hygiene indicators. This is a preliminary visual review, not an official inspection." />
      <div className="grid gap-6 lg:grid-cols-[24rem_1fr]">
        <Card className="h-fit space-y-4">
          <Dropzone files={files} onChange={(f) => { setFiles(f); frames.reset(); report.reset(); }} accept="image+video" multiple maxImageMb={limits.maxImageMb} maxVideoMb={limits.maxVideoMb} label="Drop a kitchen video or photos" />
          <div className="grid grid-cols-2 gap-3">
            <Field label="Frame every (s)" htmlFor="int" tip="Seconds between extracted video frames."><input id="int" className="input" inputMode="decimal" value={interval} onChange={(e) => setInterval_(e.target.value)} /></Field>
            <Field label="Max frames" htmlFor="mf"><input id="mf" className="input" inputMode="numeric" value={maxFrames} onChange={(e) => setMaxFrames(e.target.value)} /></Field>
          </div>
          <details className="rounded-xl border border-stone-200 p-3 dark:border-white/10">
            <summary className="cursor-pointer text-sm font-medium">Scoring criteria and weights</summary>
            <div className="mt-3 space-y-3">
              {crit.data && Object.entries(crit.data.criteria).map(([k, v]) => (
                <label key={k} className="block text-xs"><span className="flex justify-between"><span>{v.label}</span><span className="tabular-nums">{weights[k] ?? v.weight}</span></span>
                  <input type="range" min={0} max={50} className="w-full accent-emerald-600" value={weights[k] ?? v.weight} onChange={(e) => setWeights({ ...weights, [k]: Number(e.target.value) })} /></label>
              ))}
              <label className="block text-xs"><span className="flex justify-between"><span>Minimum evidence needed to score <Tip text="If less than this share of the weighted criteria can be assessed, no score is given." /></span><span>{Math.round(minCov * 100)}%</span></span>
                <input type="range" min={0} max={100} className="w-full accent-emerald-600" value={minCov * 100} onChange={(e) => setMinCov(Number(e.target.value) / 100)} /></label>
              <p className="hint">The score only reflects criteria that could actually be assessed.</p>
            </div>
          </details>
          {formError && <Alert tone="error">{formError}</Alert>}
          <div className="grid grid-cols-2 gap-3">
            <Button variant="ghost" loading={frames.loading} onClick={preview}>Preview frames</Button>
            <Button loading={report.loading} onClick={analyze}>Analyse</Button>
          </div>
        </Card>

        <div className="space-y-5" aria-live="polite">
          <ErrorAlert error={report.error ?? frames.error} />
          {frames.data && !r && (
            <Card><h2 className="mb-3 text-lg font-bold">Extracted frames ({frames.data.frames.length})</h2><FrameGrid items={frames.data.frames} /></Card>
          )}
          {report.loading && <Card><ResultSkeleton /></Card>}
          {!r && !frames.data && !report.loading && !report.error && (
            <EmptyState icon={<ShieldCheck className="h-10 w-10" />} title="No review yet">Upload footage, preview the frames the system will look at, then run the analysis.</EmptyState>
          )}
          {r && !report.loading && <Report r={r} />}
        </div>
      </div>
    </>
  );
}

function FrameGrid({ items }: { items: FramePreview[] }) {
  return (
    <ul className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4">
      {items.map((f) => (
        <li key={f.index}><img alt={`Frame at ${f.timestamp_s}s`} className="aspect-video w-full rounded-lg object-cover" src={`data:image/jpeg;base64,${f.jpeg_b64}`} /><p className="mt-1 text-xs text-stone-500">{f.timestamp_s}s</p></li>
      ))}
    </ul>
  );
}

function Report({ r }: { r: HygieneReport }) {
  const s = r.score;
  const tone = s.rating === "good" ? "green" : s.rating === "needs_attention" ? "amber" : s.rating === "poor" ? "red" : "neutral";
  return (
    <Card className="space-y-6">
      {r.status === "detector_unavailable" && <Alert tone="info" title="No vision detector configured">Frames were extracted and quality-checked, but no hygiene criteria could be assessed. {r.detector_error} Nothing was inferred.</Alert>}
      {r.status === "detector_error" && <Alert tone="warn" title="The vision model failed">{r.detector_error}</Alert>}
      {r.status === "no_usable_frames" && <Alert tone="warn" title="No usable frames">All frames were too dark or blurry to assess.</Alert>}
      <div className="flex flex-wrap items-center gap-4">
        <div className="grid h-24 w-24 place-items-center rounded-2xl bg-emerald-50 font-display text-3xl font-bold dark:bg-emerald-500/10" aria-label="Hygiene score">{s.score ?? "-"}</div>
        <div><Badge tone={tone}>{titleCase(s.rating)}</Badge>
          <p className="mt-1 text-sm text-stone-600 dark:text-slate-400">Evidence coverage {Math.round(s.coverage * 100)}% of weighted criteria. {s.message}</p></div>
      </div>

      <div><h3 className="mb-2 text-sm font-semibold">Criteria</h3>
        <ul className="divide-y divide-stone-100 rounded-xl border border-stone-200 text-sm dark:divide-white/10 dark:border-white/10">
          {Object.entries(r.criteria).map(([k, c]) => (
            <li key={k} className="flex items-center justify-between gap-3 px-3 py-2"><span>{c.label}</span>
              <Badge tone={c.status === "pass" ? "green" : c.status === "violation" ? (SEV[c.severity as keyof typeof SEV] ?? "amber") : "neutral"}>{c.status === "not_assessed" ? "Not assessed" : c.status === "pass" ? "No issue seen" : `Issue (${c.severity})`}</Badge></li>
          ))}
        </ul></div>

      {r.issues.length > 0 && (
        <div><h3 className="mb-2 text-sm font-semibold">Detected issues</h3>
          <ul className="space-y-2">{r.issues.map((i, n) => (
            <li key={n} className="rounded-xl border border-stone-200 p-3 text-sm dark:border-white/10"><div className="flex flex-wrap items-center gap-2"><Badge tone={SEV[i.severity as keyof typeof SEV] ?? "amber"}>{i.severity}</Badge><strong>{i.label}</strong><span className="text-xs text-stone-500">at {i.timestamp_s ?? "-"}s, frame {i.frame}</span></div><p className="mt-1">{i.evidence}</p></li>
          ))}</ul></div>
      )}
      {r.previews.length > 0 && <div><h3 className="mb-2 text-sm font-semibold">Associated frames</h3><FrameGrid items={r.previews} /></div>}
      {r.corrective_actions.length > 0 && <div><h3 className="mb-2 text-sm font-semibold">Recommended corrective actions</h3><ul className="list-disc space-y-1 pl-5 text-sm">{r.corrective_actions.map((a) => <li key={a}>{a}</li>)}</ul></div>}
      <div><h3 className="mb-2 text-sm font-semibold">Not observable from video</h3><ul className="list-disc space-y-1 pl-5 text-sm text-stone-600 dark:text-slate-400">{r.unobservable_criteria.map((u) => <li key={u}>{u}</li>)}</ul></div>
      {r.notes.length > 0 && <ul className="space-y-1 text-xs text-stone-500">{r.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
      <div className="flex flex-wrap gap-3">
        <Button variant="ghost" onClick={() => download("hygiene-report.md", r.report_markdown, "text/markdown")}><Download className="h-4 w-4" /> Download report</Button>
        <SaveButton kind="hygiene_report" payload={r} />
      </div>
      <Disclaimer>{r.disclaimer}</Disclaimer>
    </Card>
  );
}
