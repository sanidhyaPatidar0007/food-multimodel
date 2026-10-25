import { CalendarDays, ChefHat, FileText, Leaf, ScanLine, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip as RTooltip, XAxis, YAxis } from "recharts";
import { Alert, Badge, Card, EmptyState, ErrorAlert, ProgressBar, Skeleton } from "../components/ui";
import { useQuery } from "../hooks/useAsync";
import { get } from "../services/api";
import type { DashboardSummary } from "../types/api";
import { fmt, localDate, titleCase, when } from "../utils/format";

const ACTIONS = [
  { to: "/food", title: "Food Scanner", text: "Identify a dish and estimate its nutrition.", icon: ScanLine, tone: "bg-emerald-600" },
  { to: "/freshness", title: "Freshness Check", text: "Look for visible signs of spoilage.", icon: Leaf, tone: "bg-saffron-500" },
  { to: "/hygiene", title: "Hygiene Monitor", text: "Screen kitchen footage for visible issues.", icon: ShieldCheck, tone: "bg-sky-600" },
  { to: "/kitchen", title: "Smart Kitchen", text: "Recipes from what you have at home.", icon: ChefHat, tone: "bg-tangerine-500" },
  { to: "/meal-planner", title: "Meal Planner", text: "Allergy-safe plans and shopping lists.", icon: CalendarDays, tone: "bg-emerald-700" },
  { to: "/reports", title: "Reports", text: "Everything you chose to save.", icon: FileText, tone: "bg-stone-600" },
];
const KIND_LABEL: Record<string, string> = { food_analysis: "Food analysis", freshness_analysis: "Freshness check", hygiene_report: "Hygiene review", saved_recipe: "Saved recipe", meal_plan: "Meal plan", profile: "Preferences", intake_log: "Intake logged", shopping_list: "Shopping list" };

export default function Overview() {
  const q = useQuery(() => get<DashboardSummary>("/dashboard/summary", { today: localDate() }), []);
  const s = q.data;
  const hour = new Date().getHours();
  const greeting = hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
  const target = s?.targets;

  return (
    <div className="space-y-8">
      <header>
        <h1 className="text-3xl font-bold sm:text-4xl">{greeting}. What are we eating today?</h1>
        <p className="mt-2 max-w-2xl text-stone-600 dark:text-slate-400">Scan a plate, check a lemon, plan the week. Results are estimates and preliminary assessments.</p>
      </header>

      <section aria-label="Quick actions" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {ACTIONS.map(({ to, title, text, icon: Icon, tone }) => (
          <Link key={to} to={to} className="card group flex items-start gap-4 p-5 transition hover:-translate-y-0.5 hover:border-emerald-300">
            <span className={`grid h-11 w-11 shrink-0 place-items-center rounded-xl text-white ${tone}`}><Icon className="h-5 w-5" /></span>
            <span><span className="block font-display text-lg font-semibold">{title}</span><span className="text-sm text-stone-600 dark:text-slate-400">{text}</span></span>
          </Link>
        ))}
      </section>

      <ErrorAlert error={q.error} onRetry={q.reload} />
      {q.loading && !s && <div className="grid gap-4 lg:grid-cols-3"><Skeleton className="h-56" /><Skeleton className="h-56" /><Skeleton className="h-56" /></div>}

      {s && (
        <div className="grid gap-6 lg:grid-cols-3">
          <Card className="space-y-4 lg:col-span-1">
            <h2 className="text-lg font-bold">Today's nutrition</h2>
            {!s.today || s.today.kcal === 0 ? <EmptyState title="Nothing logged today">Log a scanned food or a planned meal to track progress.</EmptyState> : (
              <>
                <ProgressBar label="Calories" value={s.today.kcal} max={target?.calories ?? 2000} sub={`${fmt(s.today.kcal)} / ${target?.calories ?? 2000} kcal`} />
                <ProgressBar label="Protein" value={s.today.protein_g} max={target?.macros_g.protein ?? 50} color="bg-emerald-400" sub={`${fmt(s.today.protein_g)} g`} />
                <ProgressBar label="Carbs" value={s.today.carbs_g} max={target?.macros_g.carbs ?? 275} color="bg-saffron-500" sub={`${fmt(s.today.carbs_g)} g`} />
                <ProgressBar label="Fat" value={s.today.fat_g} max={target?.macros_g.fat ?? 78} color="bg-tangerine-500" sub={`${fmt(s.today.fat_g)} g`} />
                {!target && <p className="hint">No personal target yet, so a general 2,000 kcal reference is shown. Create a meal plan to set one.</p>}
              </>)}
          </Card>

          <Card className="lg:col-span-2">
            <h2 className="mb-3 text-lg font-bold">Calories this week</h2>
            {s.weekly.every((d) => d.kcal === 0) ? <EmptyState title="No intake logged this week">Your last seven days will chart here.</EmptyState> : (
              <div className="h-56" role="img" aria-label="Bar chart of calories logged per day this week">
                <ResponsiveContainer><BarChart data={s.weekly.map((d) => ({ ...d, day: new Date(d.date + "T00:00").toLocaleDateString(undefined, { weekday: "short" }) }))}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} opacity={0.3} /><XAxis dataKey="day" tickLine={false} /><YAxis tickLine={false} width={40} />
                  <RTooltip formatter={(v: number) => `${fmt(v)} kcal`} /><Bar dataKey="kcal" fill="#059669" radius={[6, 6, 0, 0]} />
                </BarChart></ResponsiveContainer>
              </div>)}
          </Card>

          <Card className="space-y-3">
            <h2 className="text-lg font-bold">Food safety alerts</h2>
            {s.alerts.length === 0 ? <p className="text-sm text-stone-500">No alerts from your saved freshness checks or hygiene reviews.</p> :
              s.alerts.map((a) => <Alert key={a.id} tone={a.severity === "high" ? "error" : "warn"} title={titleCase(a.source)}>{a.message}</Alert>)}
          </Card>

          <Card className="space-y-3">
            <h2 className="text-lg font-bold">Meal plan</h2>
            {!s.meal_plan ? <EmptyState title="No plan yet" action={<Link className="btn btn-primary" to="/meal-planner">Plan meals</Link>}>Generate an allergy-safe plan.</EmptyState> : (
              <><p className="text-sm text-stone-500">{s.meal_plan.days}-day plan - created {when(s.meal_plan.created_at)}</p>
                <ul className="space-y-1 text-sm">{s.meal_plan.today_meals.map((m) => <li key={m} className="rounded-lg bg-emerald-50 px-3 py-1.5 dark:bg-emerald-500/10">{m}</li>)}</ul>
                <Link to="/meal-planner" className="text-sm font-semibold text-emerald-700 dark:text-emerald-400">Open plan</Link></>)}
          </Card>

          <Card className="space-y-3">
            <h2 className="text-lg font-bold">Recent analyses</h2>
            {s.recent_analyses.length === 0 ? <p className="text-sm text-stone-500">Saved analyses appear here.</p> :
              <ul className="space-y-2 text-sm">{s.recent_analyses.slice(0, 5).map((r) => <li key={r.id} className="flex items-center justify-between gap-2"><span className="truncate">{r.title}</span><Badge>{KIND_LABEL[r.kind] ?? r.kind}</Badge></li>)}</ul>}
          </Card>

          <Card className="space-y-3 lg:col-span-3">
            <h2 className="text-lg font-bold">Recent activity</h2>
            {s.recent_activity.length === 0 ? <p className="text-sm text-stone-500">No activity yet. Everything you save or log shows up here.</p> :
              <ul className="grid gap-2 text-sm sm:grid-cols-2">{s.recent_activity.map((a) => <li key={a.id} className="flex justify-between rounded-lg border border-stone-100 px-3 py-2 dark:border-white/10"><span>{KIND_LABEL[a.kind] ?? a.kind}</span><span className="text-stone-500">{when(a.created_at)}</span></li>)}</ul>}
          </Card>
        </div>
      )}
    </div>
  );
}
