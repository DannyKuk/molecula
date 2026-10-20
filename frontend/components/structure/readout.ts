import type { SceneData, ViewMode } from "./scene";

/**
 * The counts in the corner of the 3D view: the drug's atoms and, in a complex, the residues within
 * 4 Å and the hydrogen bonds. Hydrogens aren't counted, since a PDB structure seldom has them and a
 * PubChem conformer has them all, so the same drug gets the same count either way.
 */
export function readout(data: SceneData): string[] {
  if (data.kind === "molecule") {
    const elements = sdfHeavyElements(data.sdf);
    return elements === null ? [] : [count(elements.length, "atom")];
  }
  const { ligand, pocket, contacts } = data.complex;
  return [
    count(ligand.atoms.filter((atom) => atom.element !== "H").length, "atom"),
    count(pocket.length, "residue"),
    count(contacts.filter((contact) => contact.kind === "hbond").length, "H-bond"),
  ];
}

/** The elements the legend explains beside the drug's carbons, as it names them. */
export const ELEMENT_NAMES: Record<string, string> = { N: "nitrogen", O: "oxygen", S: "sulfur" };

/** Which of those elements the view draws in `mode`: the drug's, and outside Molecule view also the
 * pocket's. */
export function legendElements(data: SceneData, mode: ViewMode): string[] {
  const drawn = new Set(
    data.kind === "molecule"
      ? (sdfHeavyElements(data.sdf) ?? [])
      : [
          ...data.complex.ligand.atoms,
          ...(mode === "molecule" ? [] : data.complex.pocket.flatMap((residue) => residue.atoms)),
        ].map((atom) => atom.element),
  );
  return Object.keys(ELEMENT_NAMES).filter((element) => drawn.has(element));
}

/** The elements of the atoms other than hydrogen in a V2000 molfile, or null if it has no counts
 * line. */
function sdfHeavyElements(sdf: string): string[] | null {
  const lines = sdf.split(/\r?\n/);
  const atoms = Number.parseInt(lines[3]?.slice(0, 3) ?? "", 10);
  if (Number.isNaN(atoms)) return null;
  return lines
    .slice(4, 4 + atoms)
    .map((line) => line.trim().split(/\s+/)[3])
    .filter((element) => element !== "H");
}

function count(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
}
