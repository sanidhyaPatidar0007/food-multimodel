export const fmt = (n: number | null | undefined, d = 0) => (n == null || Number.isNaN(n) ? "-" : n.toLocaleString(undefined, { maximumFractionDigits: d }));
export const pct = (v: number, max: number) => (max > 0 ? Math.min(100, Math.round((v / max) * 100)) : 0);
export const when = (iso: string) => new Date(iso).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
export const titleCase = (s: string) => s.replace(/[_-]/g, " ").replace(/^\w/, (c) => c.toUpperCase());
export function qty(n: number | null, unit: string) {
  if (n == null) return unit;
  const v = Number.isInteger(n) ? n : Math.round(n * 100) / 100;
  return `${v} ${unit}`.trim();
}
export function download(filename: string, text: string, mime = "text/plain") {
  const url = URL.createObjectURL(new Blob([text], { type: mime }));
  const a = Object.assign(document.createElement("a"), { href: url, download: filename });
  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
}
/** The user's local calendar date (YYYY-MM-DD). toISOString() would give the UTC date, which is wrong near midnight. */
export function localDate(d: Date = new Date()): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
}
