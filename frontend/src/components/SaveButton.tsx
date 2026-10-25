import { Check, Save } from "lucide-react";
import { useState } from "react";
import { post } from "../services/api";
import { useAsync } from "../hooks/useAsync";
import { Button, ErrorAlert } from "./ui";

/** Saves a result to history only when the user asks (nothing is stored automatically). */
export function SaveButton({ kind, payload, label = "Save to history" }: { kind: string; payload: unknown; label?: string }) {
  const { run, loading, error } = useAsync<unknown>();
  const [saved, setSaved] = useState(false);
  return (
    <div className="space-y-2">
      <Button variant="soft" loading={loading} disabled={saved} onClick={async () => { if (await run(() => post("/history", { kind, payload }))) setSaved(true); }}>
        {saved ? <><Check className="h-4 w-4" /> Saved</> : <><Save className="h-4 w-4" /> {label}</>}
      </Button>
      <ErrorAlert error={error} />
    </div>
  );
}
