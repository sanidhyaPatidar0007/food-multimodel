import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, normalizeError } from "../services/api";

export function useAsync<T>() {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [loading, setLoading] = useState(false);
  const alive = useRef(true);
  // Must set true on (re)mount: React StrictMode runs mount -> cleanup -> mount in dev, and without this the
  // flag stayed false forever and every page hung on its loading state.
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  const run = useCallback(async (fn: () => Promise<T>) => {
    setLoading(true); setError(null);
    try { const r = await fn(); if (alive.current) setData(r); return r; }
    catch (e) { if (alive.current) setError(normalizeError(e)); return null; }
    finally { if (alive.current) setLoading(false); }
  }, []);
  const reset = useCallback(() => { setData(null); setError(null); }, []);
  return { data, error, loading, run, reset, setData };
}

/** Fetch on mount (and when deps change) with loading / error / reload. */
export function useQuery<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const a = useAsync<T>();
  const { run } = a;
  const reload = useCallback(() => run(fn), deps); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { reload(); }, [reload]);
  return { ...a, reload };
}
