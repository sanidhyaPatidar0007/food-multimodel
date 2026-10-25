import { Download, FileText, Trash2 } from "lucide-react";
import { useState } from "react";
import { Badge, Button, Card, EmptyState, ErrorAlert, PageHeader, Skeleton } from "../components/ui";
import { useAsync, useQuery } from "../hooks/useAsync";
import { del, getMeta } from "../services/api";
import type { HistoryRecord } from "../types/api";
import { download, titleCase, when } from "../utils/format";

const KINDS = ["", "food_analysis", "freshness_analysis", "hygiene_report", "saved_recipe", "meal_plan", "intake_log"];
const PAGE = 20;

function title(r: HistoryRecord) {
  const p = r.payload;
  return p.title ?? p.food_name ?? p.name ?? p.verdict_label ?? (p.score ? `Hygiene review (${titleCase(p.score.rating)})` : p.days ? `${p.days.length}-day meal plan` : titleCase(r.kind));
}

export default function Reports() {
  const [kind, setKind] = useState(""); const [page, setPage] = useState(0); const [open, setOpen] = useState<string | null>(null);
  const q = useQuery(() => getMeta<HistoryRecord[]>("/history", { kind: kind || undefined, limit: PAGE, offset: page * PAGE }), [kind, page]);
  const rm = useAsync<unknown>();
  const items = q.data?.data ?? []; const total = (q.data?.meta.total as number) ?? 0;

  return (
    <>
      <PageHeader title="Reports" icon={<FileText className="h-6 w-6" />} description="Everything you chose to save. Uploaded photos and videos are never stored, only the results." />
      <Card className="space-y-4">
        <div className="flex flex-wrap items-center gap-3">
          <label className="text-sm font-medium" htmlFor="kind">Show</label>
          <select id="kind" className="input !w-auto" value={kind} onChange={(e) => { setKind(e.target.value); setPage(0); }}>{KINDS.map((k) => <option key={k} value={k}>{k ? titleCase(k) : "All records"}</option>)}</select>
          <span className="text-sm text-stone-500">{total} record{total === 1 ? "" : "s"}</span>
        </div>
        <ErrorAlert error={q.error ?? rm.error} onRetry={q.reload} />
        {q.loading && !q.data && <div className="space-y-2"><Skeleton className="h-14" /><Skeleton className="h-14" /><Skeleton className="h-14" /></div>}
        {q.data && items.length === 0 && <EmptyState icon={<FileText className="h-10 w-10" />} title="Nothing saved yet">Save a food analysis, freshness check, hygiene report or recipe and it will show up here.</EmptyState>}
        <ul className="space-y-2">
          {items.map((r) => (
            <li key={r.id} className="rounded-xl border border-stone-200 dark:border-white/10">
              <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
                <button className="min-w-0 flex-1 text-left" onClick={() => setOpen(open === r.id ? null : r.id)} aria-expanded={open === r.id}>
                  <span className="block truncate font-semibold">{title(r)}</span><span className="text-xs text-stone-500">{when(r.created_at)}</span></button>
                <Badge>{titleCase(r.kind)}</Badge>
                <Button variant="ghost" aria-label="Download JSON" onClick={() => download(`${r.kind}-${r.id.slice(0, 8)}.json`, JSON.stringify(r.payload, null, 2), "application/json")}><Download className="h-4 w-4" /></Button>
                <Button variant="danger" aria-label="Delete record" loading={rm.loading && open === r.id} onClick={async () => { setOpen(r.id); if (await rm.run(() => del(`/history/${r.id}`))) q.reload(); }}><Trash2 className="h-4 w-4" /></Button>
              </div>
              {open === r.id && <pre className="max-h-80 overflow-auto border-t border-stone-100 bg-stone-50 p-4 text-xs dark:border-white/10 dark:bg-white/5">{JSON.stringify(r.payload, null, 2)}</pre>}
            </li>))}
        </ul>
        {total > PAGE && <div className="flex justify-between"><Button variant="ghost" disabled={page === 0} onClick={() => setPage(page - 1)}>Previous</Button><Button variant="ghost" disabled={(page + 1) * PAGE >= total} onClick={() => setPage(page + 1)}>Next</Button></div>}
      </Card>
    </>
  );
}
