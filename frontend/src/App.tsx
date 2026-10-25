import { lazy, Suspense } from "react";
import { Route, Routes } from "react-router-dom";
import AppLayout from "./layouts/AppLayout";
import { Skeleton } from "./components/ui";

const Overview = lazy(() => import("./pages/Overview"));
const FoodScanner = lazy(() => import("./pages/FoodScanner"));
const Freshness = lazy(() => import("./pages/Freshness"));
const Hygiene = lazy(() => import("./pages/Hygiene"));
const Kitchen = lazy(() => import("./pages/Kitchen"));
const MealPlanner = lazy(() => import("./pages/MealPlanner"));
const Reports = lazy(() => import("./pages/Reports"));
const SettingsPage = lazy(() => import("./pages/SettingsPage"));

export default function App() {
  return (
    <Suspense fallback={<div className="p-8"><Skeleton className="h-10 w-1/3" /></div>}>
      <Routes>
        <Route element={<AppLayout />}>
          <Route index element={<Overview />} />
          <Route path="food" element={<FoodScanner />} />
          <Route path="freshness" element={<Freshness />} />
          <Route path="hygiene" element={<Hygiene />} />
          <Route path="kitchen" element={<Kitchen />} />
          <Route path="meal-planner" element={<MealPlanner />} />
          <Route path="reports" element={<Reports />} />
          <Route path="settings" element={<SettingsPage />} />
          <Route path="*" element={<p className="py-20 text-center">Page not found.</p>} />
        </Route>
      </Routes>
    </Suspense>
  );
}
