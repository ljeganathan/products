import { isAxiosError } from "axios";

/** Extracts FastAPI's `{detail: string | {msg: string}[]}` error shape into
 * a single displayable string, falling back to a generic message. */
export function getApiErrorMessage(err: unknown, fallback: string): string {
  if (isAxiosError(err)) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((d) => (typeof d === "string" ? d : d.msg)).join(", ");
    }
  }
  return fallback;
}
