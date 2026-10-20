import type { SceneData } from "./scene";

/**
 * The counts in the corner of the 3D view: the drug's atoms and, in a complex, the residues within
 * 4 Å and the hydrogen bonds. Hydrogens aren't counted, since a PDB structure seldom has them and a
 * PubChem conformer has them all, so the same drug gets the same count either way.
 */
export function readout(data: SceneData): string[] {
  if (data.kind === "molecule") {
    const atoms = sdfHeavyAtoms(data.sdf);
    return atoms === null ? [] : [count(atoms, "atom")];
  }
  const { ligand, pocket, contacts } = data.complex;
  return [
    count(ligand.atoms.filter((atom) => atom.element !== "H").length, "atom"),
    count(pocket.length, "residue"),
    count(contacts.filter((contact) => contact.kind === "hbond").length, "H-bond"),
  ];
}

/** The atoms other than hydrogen in a V2000 molfile, or null if it has no counts line. */
function sdfHeavyAtoms(sdf: string): number | null {
  const lines = sdf.split(/\r?\n/);
  const atoms = Number.parseInt(lines[3]?.slice(0, 3) ?? "", 10);
  if (Number.isNaN(atoms)) return null;
  return lines.slice(4, 4 + atoms).filter((line) => line.trim().split(/\s+/)[3] !== "H").length;
}

function count(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
}
