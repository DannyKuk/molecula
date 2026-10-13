import type { Resolution, Suggestion } from "@/lib/api";

/** The backend's answer for a name outside the supported drugs. */
export function notSupported(query: string, suggestions: Suggestion[] = []): Resolution {
  return {
    query,
    status: "not_supported",
    compound: null,
    matched_alias: null,
    match_kind: null,
    suggestions,
  };
}
