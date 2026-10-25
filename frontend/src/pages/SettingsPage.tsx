import { Moon, Settings, Sun } from "lucide-react";
import { Alert, Badge, Button, Card, ErrorAlert, PageHeader, Skeleton } from "../components/ui";
import { useQuery } from "../hooks/useAsync";
import { useTheme } from "../hooks/useTheme";
import { API_BASE_URL, get } from "../services/api";
import type { Health } from "../types/api";
import { titleCase } from "../utils/format";

export default function SettingsPage() {
  const { dark, toggle } = useTheme();
  const h = useQuery(() => get<Health>("/health"), []);
  return (
    <>
      <PageHeader title="Settings" icon={<Settings className="h-6 w-6" />} description="Appearance and the status of the AI providers behind each module." />
      <div className="grid gap-6 lg:grid-cols-2">
        <Card className="space-y-4"><h2 className="text-lg font-bold">Appearance</h2>
          <Button variant="ghost" onClick={toggle}>{dark ? <><Sun className="h-4 w-4" /> Switch to light mode</> : <><Moon className="h-4 w-4" /> Switch to dark mode</>}</Button></Card>

        <Card className="space-y-3"><h2 className="text-lg font-bold">Connection</h2>
          <dl className="text-sm"><dt className="text-stone-500">API base URL</dt><dd className="font-mono">{API_BASE_URL}</dd></dl>
          {h.loading && <Skeleton className="h-16" />}<ErrorAlert error={h.error} onRetry={h.reload} />
          {h.data && <dl className="grid grid-cols-2 gap-2 text-sm"><dt className="text-stone-500">Status</dt><dd><Badge tone={h.data.status === "ok" ? "green" : "red"}>{h.data.status}</Badge></dd><dt className="text-stone-500">Version</dt><dd>{h.data.version}</dd><dt className="text-stone-500">Environment</dt><dd>{h.data.environment}</dd>
            <dt className="text-stone-500">Upload limits</dt><dd>{h.data.limits.max_image_mb} MB image, {h.data.limits.max_video_mb} MB / {h.data.limits.max_video_seconds}s video</dd></dl>}
        </Card>

        <Card className="space-y-3 lg:col-span-2"><h2 className="text-lg font-bold">AI providers</h2>
          <p className="text-sm text-stone-600 dark:text-slate-400">Providers are configured on the server (see <code>backend/.env</code>). Keys are never sent to or shown in the browser.</p>
          {h.data && <ul className="divide-y divide-stone-100 rounded-xl border border-stone-200 dark:divide-white/10 dark:border-white/10">
            {Object.entries(h.data.providers).map(([k, v]) => (
              <li key={k} className="flex flex-wrap items-center justify-between gap-2 px-4 py-3 text-sm"><span className="font-medium">{titleCase(k)}</span><span className="flex items-center gap-2 text-stone-500">{v.detail}<Badge tone={v.configured ? "green" : "amber"}>{v.configured ? "Active" : "Not configured"}</Badge></span></li>))}
          </ul>}
          <Alert tone="info" title="Privacy">Uploaded photos and videos are processed in memory and are not stored. Only results you choose to save are kept in the local database on the server.</Alert>
        </Card>
      </div>
    </>
  );
}
