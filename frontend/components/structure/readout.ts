import { en, type Messages } from "@/lib/messages";

import type { SceneData, ViewMode } from "./scene";

/**
 * The counts in the corner of the 3D view: the drug's atoms and, in a complex, the residues within
 * 4 Å and the hydrogen bonds. Hydrogens aren't counted, since a PDB structure seldom has them and a
 * PubChem conformer has them all, so the same drug gets the same count either way.
 */
export function readout(data: SceneData, t: Messages = en): string[] {
  const { atoms, residues, hBonds } = t.structure;
  if (data.kind === "molecule") {
    const elements = sdfElements(data.sdf);
    return elements === null ? [] : [atoms(elements.filter((element) => element !== "H").length)];
  }
  const { ligand, pocket, contacts } = data.complex;
  return [
    atoms(ligand.atoms.filter((atom) => atom.element !== "H").length),
    residues(pocket.length),
    hBonds(contacts.filter((contact) => contact.kind === "hbond").length),
  ];
}

/** The elements the legend explains beside the drug's carbons, in the order of a molecular formula
 * after its carbons: hydrogen, then the rest alphabetically. The dictionaries name them
 * (`structure.elements`). */
export const LEGEND_ELEMENTS = ["H", "Cl", "F", "I", "N", "O", "P", "S"];

/** Which of those elements the view draws in `mode`: the drug's, and outside Molecule view also the
 * pocket's. */
export function legendElements(data: SceneData, mode: ViewMode): string[] {
  const drawn = new Set(
    data.kind === "molecule"
      ? (sdfElements(data.sdf) ?? [])
      : [
          ...data.complex.ligand.atoms,
          ...(mode === "molecule" ? [] : data.complex.pocket.flatMap((residue) => residue.atoms)),
        ].map((atom) => atom.element),
  );
  return LEGEND_ELEMENTS.filter((element) => drawn.has(element));
}

/** The elements of the atoms in a V2000 molfile, or null if it has no counts line. */
function sdfElements(sdf: string): string[] | null {
  const lines = sdf.split(/\r?\n/);
  const atoms = Number.parseInt(lines[3]?.slice(0, 3) ?? "", 10);
  if (Number.isNaN(atoms)) return null;
  return lines.slice(4, 4 + atoms).map((line) => line.trim().split(/\s+/)[3]);
}
