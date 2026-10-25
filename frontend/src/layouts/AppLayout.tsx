import { CalendarDays, ChefHat, FileText, LayoutDashboard, Leaf, Menu, Moon, ScanLine, Settings, ShieldCheck, Sun, X } from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useTheme } from "../hooks/useTheme";
import { useQuery } from "../hooks/useAsync";
import { get } from "../services/api";
import type { Health } from "../types/api";

export const NAV = [
  { to: "/", label: "Overview", icon: LayoutDashboard, end: true },
  { to: "/food", label: "Food Scanner", icon: ScanLine },
  { to: "/freshness", label: "Freshness Check", icon: Leaf },
  { to: "/hygiene", label: "Hygiene Monitor", icon: ShieldCheck },
  { to: "/kitchen", label: "Smart Kitchen", icon: ChefHat },
  { to: "/meal-planner", label: "Meal Planner", icon: CalendarDays },
  { to: "/reports", label: "Reports", icon: FileText },
  { to: "/settings", label: "Settings", icon: Settings },
];

export default function AppLayout() {
  const [open, setOpen] = useState(false);
  const { dark, toggle } = useTheme();
  const health = useQuery(() => get<Health>("/health"), []);
  const online = health.data?.status === "ok";

  const links = (
    <nav aria-label="Main" className="flex flex-col gap-1">
      {NAV.map(({ to, label, icon: Icon, end }) => (
        <NavLink key={to} to={to} end={end} onClick={() => setOpen(false)}
          className={({ isActive }) => `flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition ${isActive ? "bg-emerald-600 text-white shadow-soft" : "text-slate-600 hover:bg-emerald-50 dark:text-slate-300 dark:hover:bg-white/5"}`}>
          <Icon className="h-[18px] w-[18px]" aria-hidden />{label}
        </NavLink>
      ))}
    </nav>
  );

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[17rem_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:fixed focus:left-3 focus:top-3 focus:z-50 focus:rounded-lg focus:bg-white focus:px-3 focus:py-2">Skip to content</a>
      <aside className="hidden border-r border-stone-200/80 bg-white/70 p-5 dark:border-white/10 dark:bg-night-800/60 lg:sticky lg:top-0 lg:block lg:h-screen">
        <Brand />{links}
        <p className="absolute bottom-5 left-5 right-5 text-xs text-stone-500 dark:text-slate-500">Estimates and preliminary assessments only. Not medical or regulatory advice.</p>
      </aside>

      {open && <div className="fixed inset-0 z-40 bg-black/40 lg:hidden" onClick={() => setOpen(false)} aria-hidden />}
      <aside className={`fixed inset-y-0 left-0 z-50 w-72 transform bg-cream-50 p-5 transition-transform dark:bg-night-900 lg:hidden ${open ? "translate-x-0" : "-translate-x-full"}`} aria-hidden={!open}>
        <div className="mb-4 flex items-center justify-between"><Brand /><button aria-label="Close menu" onClick={() => setOpen(false)}><X /></button></div>{links}
      </aside>

      <div className="min-w-0">
        <div className="sticky top-0 z-30 flex items-center justify-between border-b border-stone-200/80 bg-cream-50/90 px-4 py-3 backdrop-blur dark:border-white/10 dark:bg-night-900/90 sm:px-8">
          <button className="btn btn-ghost lg:hidden" aria-label="Open menu" onClick={() => setOpen(true)}><Menu className="h-5 w-5" /></button>
          <div className="hidden items-center gap-2 text-xs lg:flex" role="status">
            <span className={`h-2 w-2 rounded-full ${health.loading ? "bg-stone-400" : online ? "bg-emerald-500" : "bg-red-500"}`} />
            {health.loading ? "Checking API..." : online ? `API connected (v${health.data?.version})` : "API unreachable"}
          </div>
          <button className="btn btn-ghost" onClick={toggle} aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}>{dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}</button>
        </div>
        <main id="main" className="mx-auto max-w-6xl px-4 py-6 sm:px-8 sm:py-8"><Outlet /></main>
      </div>
    </div>
  );
}

function Brand() {
  return (
    <div className="mb-6 flex items-center gap-2.5 px-1">
      <img src="/favicon.svg" alt="" className="h-9 w-9" />
      <span className="font-display text-xl font-bold">FoodVerse <span className="text-emerald-600">AI</span></span>
    </div>
  );
}
