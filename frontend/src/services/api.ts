import axios, { AxiosError } from "axios";
import type { ApiEnvelope } from "../types/api";

export class ApiError extends Error {
  constructor(message: string, public status = 0, public code = "error", public requestId?: string, public details?: unknown) {
    super(message);
    this.name = "ApiError";
  }
}

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL || "/api/v1";
const http = axios.create({ baseURL: API_BASE_URL, timeout: 60_000 });

/** Turn any thrown value into a user-readable ApiError (never leaks internals). */
export function normalizeError(err: unknown): ApiError {
  if (err instanceof ApiError) return err;
  const e = err as AxiosError<any>;
  if (e?.isAxiosError) {
    if (e.code === "ECONNABORTED" || e.code === "ETIMEDOUT")
      return new ApiError("The request timed out. The server may be busy; please try again.", 0, "timeout");
    if (!e.response)
      return new ApiError("Cannot reach the FoodVerse server. Check that the backend is running and the API URL is correct.", 0, "network");
    const body = e.response.data;
    if (body && typeof body === "object" && body.error?.message)
      return new ApiError(body.error.message, e.response.status, body.error.code, body.error.request_id, body.error.details);
    return new ApiError(`The server returned an unexpected error (HTTP ${e.response.status}).`, e.response.status, "http_error");
  }
  return new ApiError("Something went wrong. Please try again.");
}

/** Validate the response envelope before the UI renders it. */
export function unwrap<T>(body: unknown): T {
  const b = body as ApiEnvelope<T> | undefined;
  if (!b || typeof b !== "object" || b.ok !== true || !("data" in b))
    throw new ApiError("The server sent a response in an unexpected format.", 0, "invalid_response");
  return b.data;
}

async function call<T>(p: Promise<{ data: unknown }>): Promise<T> {
  try { return unwrap<T>((await p).data); } catch (e) { throw normalizeError(e); }
}

export const get = <T,>(url: string, params?: object) => call<T>(http.get(url, { params }));
export const post = <T,>(url: string, body?: unknown, timeout?: number) => call<T>(http.post(url, body, { timeout }));
export const patch = <T,>(url: string, body?: unknown) => call<T>(http.patch(url, body));
export const del = <T,>(url: string) => call<T>(http.delete(url));
/** multipart/form-data upload (images / video). Longer timeout for video work. */
export const upload = <T,>(url: string, form: FormData, timeout = 60_000) =>
  call<T>(http.post(url, form, { timeout }) /* browser sets the multipart boundary */);
export async function getMeta<T>(url: string, params?: object): Promise<{ data: T; meta: Record<string, any> }> {
  try { const r = await http.get(url, { params }); return { data: unwrap<T>(r.data), meta: r.data.meta ?? {} }; } catch (e) { throw normalizeError(e); }
}
