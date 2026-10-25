import { UploadCloud, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { Alert } from "./ui";

const IMAGE = ["image/jpeg", "image/png", "image/webp"];
const VIDEO = ["video/mp4", "video/webm", "video/quicktime", "video/x-msvideo"];

interface Props {
  files: File[]; onChange: (files: File[]) => void;
  accept?: "image" | "image+video"; multiple?: boolean; maxImageMb?: number; maxVideoMb?: number; label?: string;
}

/** Drag-and-drop / click-to-browse uploader with client-side type + size validation and previews. */
export function Dropzone({ files, onChange, accept = "image", multiple = false, maxImageMb = 8, maxVideoMb = 60, label }: Props) {
  const [problem, setProblem] = useState<string | null>(null);
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const allowed = accept === "image" ? IMAGE : [...IMAGE, ...VIDEO];
  const previews = useMemo(() => files.map((f) => ({ f, url: URL.createObjectURL(f) })), [files]);
  useEffect(() => () => previews.forEach((p) => URL.revokeObjectURL(p.url)), [previews]);

  function take(list: FileList | null) {
    if (!list) return;
    const picked = Array.from(list);
    for (const f of picked) {
      if (!allowed.includes(f.type)) return setProblem(`"${f.name}" is not supported. Use ${accept === "image" ? "JPEG, PNG or WebP" : "JPEG, PNG, WebP, MP4, WebM, MOV or AVI"}.`);
      const isVideo = VIDEO.includes(f.type);
      const limit = (isVideo ? maxVideoMb : maxImageMb) * 1024 * 1024;
      if (f.size === 0) return setProblem(`"${f.name}" is empty.`);
      if (f.size > limit) return setProblem(`"${f.name}" is ${(f.size / 1048576).toFixed(1)} MB; the limit is ${isVideo ? maxVideoMb : maxImageMb} MB.`);
    }
    if (picked.some((f) => VIDEO.includes(f.type)) && (picked.length > 1 || files.length)) return setProblem("Upload either one video or several images, not both.");
    setProblem(null);
    onChange(multiple ? [...files, ...picked].filter((f) => !VIDEO.includes(f.type) || picked.includes(f)).slice(0, 24) : picked.slice(0, 1));
  }

  return (
    <div>
      <div
        role="button" tabIndex={0} aria-label={label ?? "Upload a file"}
        onClick={() => input.current?.click()}
        onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), input.current?.click())}
        onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
        onDrop={(e) => { e.preventDefault(); setOver(false); take(e.dataTransfer.files); }}
        className={`flex cursor-pointer flex-col items-center justify-center rounded-2xl border-2 border-dashed px-4 py-8 text-center transition ${over ? "border-emerald-500 bg-emerald-50 dark:bg-emerald-500/10" : "border-stone-300 hover:border-emerald-400 dark:border-white/15"}`}
      >
        <UploadCloud className="mb-2 h-8 w-8 text-emerald-600" aria-hidden />
        <p className="text-sm font-semibold">{label ?? "Drop a file here or click to browse"}</p>
        <p className="hint">{accept === "image" ? `JPEG, PNG or WebP, up to ${maxImageMb} MB` : `Images (${maxImageMb} MB each) or one video (up to ${maxVideoMb} MB)`}</p>
        <input ref={input} type="file" hidden multiple={multiple} accept={allowed.join(",")} onChange={(e) => { take(e.target.files); e.target.value = ""; }} />
      </div>
      {problem && <div className="mt-3"><Alert tone="error">{problem}</Alert></div>}
      {previews.length > 0 && (
        <ul className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {previews.map(({ f, url }, i) => (
            <li key={`${f.name}-${i}`} className="relative overflow-hidden rounded-xl border border-stone-200 dark:border-white/10">
              {VIDEO.includes(f.type) ? <video src={url} className="h-32 w-full bg-black object-cover" controls muted /> : <img src={url} alt={`Preview of ${f.name}`} className="h-32 w-full object-cover" />}
              <button type="button" aria-label={`Remove ${f.name}`} onClick={() => onChange(files.filter((_, j) => j !== i))} className="absolute right-1.5 top-1.5 rounded-full bg-black/60 p-1 text-white hover:bg-black/80"><X className="h-3.5 w-3.5" /></button>
              <p className="truncate px-2 py-1 text-xs text-stone-600 dark:text-slate-400">{f.name}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
