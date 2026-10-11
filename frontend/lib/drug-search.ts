import type { Drug } from "./api";

/** The drugs whose name or one of whose aliases contains the query, ignoring case. */
export function filterDrugs(drugs: Drug[], query: string): Drug[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return drugs;
  return drugs.filter((drug) =>
    [drug.name, ...drug.aliases].some((term) => term.toLowerCase().includes(needle)),
  );
}
