import { AlertTriangle, CheckCircle2, Info, Loader2, XCircle } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";
import type { ApiError } from "../services/api";

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <section className={`card p-5 sm:p-6 ${className}`}>{children}</section>;
}

export function PageHeader({ title, description, icon, actions }: { title: string; description: string; icon?: ReactNode; actions?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-start justify-between gap-4">
      <div className="flex items-start gap-3">
        {icon && <div className="mt-1 grid h-11 w-11 shrink-0 place-items-center rounded-xl bg-emerald-600 text-white">{icon}</div>}
        <div>
          <h1 className="text-2xl font-bold sm:text-3xl">{title}</h1>
          <p className="mt-1 max-w-2xl text-sm text-stone-600 dark:text-slate-400">{description}</p>
        </div>
      </div>
      {actions}
    </header>
  );
}

export function Button({ variant = "primary", loading, children, className = "", ...rest }:
  ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "soft" | "ghost" | "danger"; loading?: boolean }) {
  return (
    <button {...rest} disabled={rest.disabled || loading} className={`btn btn-${variant} ${className}`}>
      {loading && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />}
      {children}
    </button>
  );
}

const tones = {
  info: { cls: "border-sky-200 bg-sky-50 text-sky-900 dark:border-sky-400/30 dark:bg-sky-500/10 dark:text-sky-200", Icon: Info },
  warn: { cls: "border-amber-300 bg-amber-50 text-amber-900 dark:border-amber-400/30 dark:bg-amber-500/10 dark:text-amber-200", Icon: AlertTriangle },
  error: { cls: "border-red-200 bg-red-50 text-red-900 dark:border-red-400/30 dark:bg-red-500/10 dark:text-red-200", Icon: XCircle },
  success: { cls: "border-emerald-200 bg-emerald-50 text-emerald-900 dark:border-emerald-400/30 dark:bg-emerald-500/10 dark:text-emerald-200", Icon: CheckCircle2 },
};
export function Alert({ tone = "info", title, children, action }: { tone?: keyof typeof tones; title?: string; children?: ReactNode; action?: ReactNode }) {
  const { cls, Icon } = tones[tone];
  return (
    <div role={tone === "error" ? "alert" : "status"} className={`flex gap-3 rounded-xl border p-3.5 text-sm ${cls}`}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="min-w-0 flex-1">{title && <p className="font-semibold">{title}</p>}{children && <div className={title ? "mt-0.5" : ""}>{children}</div>}</div>
      {action}
    </div>
  );
}

export function ErrorAlert({ error, onRetry }: { error: ApiError | null; onRetry?: () => void }) {
  if (!error) return null;
  return (
    <Alert tone="error" title={error.code === "clarification_needed" ? "Please adjust your preferences" : "Something went wrong"}
      action={onRetry && <button className="text-xs font-semibold underline" onClick={onRetry}>Retry</button>}>
      {error.message}{error.requestId && <span className="mt-1 block text-xs opacity-70">Reference: {error.requestId}</span>}
    </Alert>
  );
}

export function Badge({ children, tone = "neutral", title }: { children: ReactNode; tone?: "neutral" | "green" | "amber" | "red" | "blue" | "orange"; title?: string }) {
  const t = {
    neutral: "bg-stone-100 text-stone-700 dark:bg-white/10 dark:text-slate-300",
    green: "bg-emerald-100 text-emerald-800 dark:bg-emerald-500/15 dark:text-emerald-300",
    amber: "bg-amber-100 text-amber-800 dark:bg-amber-500/15 dark:text-amber-300",
    red: "bg-red-100 text-red-800 dark:bg-red-500/15 dark:text-red-300",
    blue: "bg-sky-100 text-sky-800 dark:bg-sky-500/15 dark:text-sky-300",
    orange: "bg-orange-100 text-orange-800 dark:bg-orange-500/15 dark:text-orange-300",
  }[tone];
  return <span title={title} className={`badge ${t}`}>{children}</span>;
}

/** Makes the provenance of a result explicit: real model vs. database vs. heuristic vs. fallback. */
export function SourceBadge({ kind }: { kind: "model" | "database" | "calculation" | "heuristic" | "fallback" | "llm" | "user" }) {
  const map = {
    model: ["blue", "AI model prediction"], llm: ["blue", "AI model output"], database: ["green", "Reference-table value"],
    calculation: ["neutral", "Calculated"], heuristic: ["amber", "Demo baseline (not a trained model)"],
    fallback: ["amber", "Local fallback (not AI)"], user: ["neutral", "Chosen by you"],
  } as const;
  const [tone, label] = map[kind];
  return <Badge tone={tone}>{label}</Badge>;
}

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden className={`animate-pulse rounded-lg bg-stone-200/80 dark:bg-white/10 ${className}`} />;
}

export function EmptyState({ icon, title, children, action }: { icon?: ReactNode; title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center rounded-xl border border-dashed border-stone-300 px-6 py-10 text-center dark:border-white/15">
      {icon && <div className="mb-3 text-stone-400">{icon}</div>}
      <p className="font-display text-lg font-semibold">{title}</p>
      {children && <p className="mt-1 max-w-sm text-sm text-stone-600 dark:text-slate-400">{children}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ProgressBar({ value, max, label, color = "bg-emerald-500", sub }: { value: number; max: number; label: string; color?: string; sub?: string }) {
  const p = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  return (
    <div>
      <div className="mb-1 flex justify-between text-xs"><span className="font-medium">{label}</span><span className="text-stone-500 dark:text-slate-400">{sub ?? `${Math.round(value)} / ${Math.round(max)}`}</span></div>
      <div className="h-2 overflow-hidden rounded-full bg-stone-100 dark:bg-white/10" role="progressbar" aria-valuenow={Math.round(p)} aria-valuemin={0} aria-valuemax={100} aria-label={label}>
        <div className={`h-full rounded-full ${color}`} style={{ width: `${p}%` }} />
      </div>
    </div>
  );
}

/** Keyboard- and screen-reader-accessible tooltip (native title + visible on focus/hover). */
export function Tip({ text, children }: { text: string; children?: ReactNode }) {
  return (
    <span className="group relative inline-flex">
      <span tabIndex={0} aria-label={text} className="inline-flex cursor-help items-center">{children ?? <Info className="h-3.5 w-3.5 text-stone-400" />}</span>
      <span role="tooltip" className="pointer-events-none absolute bottom-full left-1/2 z-20 mb-1 hidden w-56 -translate-x-1/2 rounded-lg bg-night-900 px-2.5 py-1.5 text-xs font-normal text-white shadow-lg group-focus-within:block group-hover:block">{text}</span>
    </span>
  );
}

export function Field({ label, hint, children, htmlFor, tip }: { label: string; hint?: string; children: ReactNode; htmlFor?: string; tip?: string }) {
  return (
    <div>
      <label className="label flex items-center gap-1.5" htmlFor={htmlFor}>{label}{tip && <Tip text={tip} />}</label>
      {children}
      {hint && <p className="hint">{hint}</p>}
    </div>
  );
}

export const Disclaimer = ({ children }: { children: ReactNode }) => (
  <p className="rounded-lg bg-stone-100 px-3 py-2 text-xs text-stone-600 dark:bg-white/5 dark:text-slate-400">{children}</p>
);

export function ResultSkeleton() {
  return <div className="space-y-3" aria-busy="true" aria-label="Analysing"><Skeleton className="h-8 w-1/2" /><Skeleton className="h-32 w-full" /><Skeleton className="h-24 w-full" /></div>;
}
