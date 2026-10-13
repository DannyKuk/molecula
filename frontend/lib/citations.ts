import type { Source } from "./chat";

/** One citation as the backend reads it (`CITATION` in `backend/src/molecula/agent/references.py`):
 * `[n]`, `[n, m]`, or gpt-oss's own `【n】`. */
const CITATION = /[[【](\d+(?:\s*,\s*\d+)*)[\]】]/;

/** Citations written next to each other, such as `[2][3]` or `[1] [4]`, which show as one chip. */
export const CITATION_RUN = new RegExp(
  String.raw`${CITATION.source}(?:\s*${CITATION.source})*`,
  "g",
);

/** The numbers in a run of citations, in order, each once. */
export function runRefs(run: string): number[] {
  return [...new Set((run.match(/\d+/g) ?? []).map(Number))];
}

/** The numbers an answer cites, in order, each once. */
export function citedRefs(answer: string): number[] {
  return [...new Set((answer.match(CITATION_RUN) ?? []).flatMap(runRefs))];
}

/** A label passage the answer can cite, as the label search returned it. */
export type Passage = { ref: number; text: string };

/** What the answer's citations point at, once the `sources` event has arrived. */
export type Citations = {
  sources: Source[];
  passages: Record<number, Passage>;
};

/** "mechanism_of_action" → "Mechanism of action". */
export function sectionName(section: string | null): string {
  if (!section) return "Label";
  const words = section.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/** The cited label sources of a run of citations; numbers that point at nothing are left out. */
export function citedSources(refs: number[], sources: Source[]): Source[] {
  return refs.flatMap((ref) => sources.filter((source) => source.ref === ref));
}

/** "Gleevec · Mechanism of action". */
export function sourceLabel(source: Source): string {
  return `${source.name} · ${sectionName(source.section)}`;
}

/** "2026-07-13" → "Jul 13, 2026". */
export function labelDate(isoDate: string): string {
  return new Date(`${isoDate}T00:00:00Z`).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}
