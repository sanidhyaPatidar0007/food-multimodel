import { useQuery } from "./useAsync";
import { get } from "../services/api";
import type { Health } from "../types/api";

/** Upload limits come from the backend /health so the UI and server agree. */
export function useLimits() {
  const { data } = useQuery(() => get<Health>("/health"), []);
  return { maxImageMb: data?.limits.max_image_mb ?? 8, maxVideoMb: data?.limits.max_video_mb ?? 60 };
}
