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

/** The sites of the sources that aren't labels, by `kind`. */
const SITE_NAMES: Record<string, string> = {
  pubchem: "PubChem",
  chembl: "ChEMBL",
  rcsb: "RCSB PDB",
};

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

/** The cited sources of a run of citations; numbers that point at nothing are left out. */
export function citedSources(refs: number[], sources: Source[]): Source[] {
  return refs.flatMap((ref) => sources.filter((source) => source.ref === ref));
}

export function isLabel(source: Source): boolean {
  return source.kind === "dailymed";
}

/** "PubChem", or the source's kind when the site isn't known. */
export function siteName(source: Source): string {
  return SITE_NAMES[source.kind] ?? source.kind;
}

/** "Gleevec · Mechanism of action" for a label passage, "PubChem · imatinib" for a page. */
export function sourceLabel(source: Source): string {
  return isLabel(source)
    ? `${source.name} · ${sectionName(source.section)}`
    : `${siteName(source)} · ${source.name}`;
}

/** One line of a source list: what the source is, its link, and the numbers the answer cites it
 * with. */
export type SourceEntry = { refs: number[]; where: string; what: string; url: string };

/** The answer's sources as a list, by the numbers the answer cites them with. Passages of the same
 * label section share one entry, with all their numbers. */
export function sourceEntries(sources: Source[]): SourceEntry[] {
  const entries = new Map<string, SourceEntry>();
  for (const source of sources) {
    const [where, what] = isLabel(source)
      ? [source.name, sectionName(source.section)]
      : [siteName(source), source.name];
    const key = `${where} – ${what} – ${source.url}`;
    const entry = entries.get(key) ?? { refs: [], where, what, url: source.url };
    if (source.ref !== null) entry.refs.push(source.ref);
    entries.set(key, entry);
  }
  return [...entries.values()];
}

/** "[1] Gleevec – Mechanism of action – https://…" for a label passage, "[4] PubChem – imatinib –
 * https://…" for a page; "[2, 3] Gleevec – Pharmacokinetics – https://…" for an entry with two. */
export function sourceLines(sources: Source[]): string[] {
  return sourceEntries(sources).map(({ refs, where, what, url }) => {
    const line = `${where} – ${what} – ${url}`;
    return refs.length ? `[${refs.join(", ")}] ${line}` : line;
  });
}

const EXCERPT_LENGTH = 320;

/** The start of a passage, as much as a popover or a source card shows. */
export function excerpt(text: string): string {
  return text.length > EXCERPT_LENGTH ? `${text.slice(0, EXCERPT_LENGTH).trimEnd()}…` : text;
}

/** "2026-07-13" → "Jul 13, 2026", or in another locale its own way ("13. Juli 2026"). */
export function labelDate(isoDate: string, locale = "en-US"): string {
  return new Date(`${isoDate}T00:00:00Z`).toLocaleDateString(locale, {
    year: "numeric",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}
