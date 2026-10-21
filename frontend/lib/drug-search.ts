import type { Drug, Resolution, Suggestion } from "./api";

/** The drugs whose name or one of whose aliases contains the query, ignoring case. */
export function filterDrugs(drugs: Drug[], query: string): Drug[] {
  const needle = query.trim().toLowerCase();
  if (!needle) return drugs;
  return drugs.filter((drug) =>
    [drug.name, ...drug.aliases].some((term) => term.toLowerCase().includes(needle)),
  );
}

export type DrugGroup = { letter: string; drugs: Drug[] };

/** The drugs grouped by the first letter of their name, in the order they come. */
export function byLetter(drugs: Drug[]): DrugGroup[] {
  const groups: DrugGroup[] = [];
  for (const drug of drugs) {
    const letter = drug.name.charAt(0).toUpperCase();
    const last = groups.at(-1);
    if (last?.letter === letter) last.drugs.push(drug);
    else groups.push({ letter, drugs: [drug] });
  }
  return groups;
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
