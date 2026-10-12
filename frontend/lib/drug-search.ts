import type { Drug, Resolution, Suggestion } from "./api";

/** The drugs whose name or one of whose aliases contains the query, ignoring case. */
export function filterDrugs(drugs: Drug[], query: string): Drug[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return drugs;
  return drugs.filter((drug) =>
    [drug.name, ...drug.aliases].some((term) => term.toLowerCase().includes(needle)),
  );
}

/**
 * The supported names to offer for a name the list doesn't match, best first. The backend also
 * knows salt names and PubChem synonyms, so a name it resolves offers the drug it resolves to.
 */
export function namesToOffer(resolution: Resolution): Suggestion[] {
  const { compound } = resolution;
  if (resolution.status === "found" && compound) {
    return [{ alias: compound.name, cid: compound.cid, name: compound.name }];
  }
  return resolution.suggestions;
}
