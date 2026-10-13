import type { AtomSelectionSpec, AtomSpec } from "3dmol";

import type { Complex, Residue, Xyz } from "./api";

export type Point = { x: number; y: number; z: number };

/** A hydrogen bond as the viewer draws it: a dashed line from the residue atom to the drug atom,
 * labelled at the residue end. */
export type HydrogenBondLine = { label: string; residue: Point; ligand: Point };

const SECONDARY_STRUCTURE = { helix: "h", sheet: "s", coil: "c" } as const;

const BOND_ORDER = { single: 1, double: 2, triple: 3, aromatic: 1.5 } as const;

const point = ([x, y, z]: Xyz): Point => ({ x, y, z });

const residueKey = (residue: Residue) => `${residue.chain}:${residue.number}:${residue.ins_code}`;

/**
 * The protein's atoms for 3Dmol: one point per residue for the backbone trace, and every heavy atom
 * of the pocket residues, which replace their trace point. Bonds come from 3Dmol's `assignBonds`.
 */
export function proteinAtoms(complex: Complex): AtomSpec[] {
  const pocket = new Map(complex.pocket.map((residue) => [residueKey(residue), residue]));
  const atoms: AtomSpec[] = [];
  const add = (residue: Residue, name: string, element: string, xyz: Xyz, ss: string) =>
    atoms.push({
      ...point(xyz),
      elem: element,
      atom: name,
      resn: residue.name,
      resi: residue.number,
      icode: residue.ins_code,
      chain: residue.chain,
      ss,
      hetflag: false,
    });
  for (const residue of complex.trace) {
    const ss = residue.sse ? SECONDARY_STRUCTURE[residue.sse] : "c";
    const pocketResidue = pocket.get(residueKey(residue));
    if (pocketResidue) {
      for (const atom of pocketResidue.atoms) add(residue, atom.name, atom.element, atom.xyz, ss);
      pocket.delete(residueKey(residue));
    } else if (residue.sse === null) {
      add(residue, "P", "P", residue.xyz, ss);
    } else {
      add(residue, "CA", "C", residue.xyz, ss);
    }
  }
  for (const residue of pocket.values()) {
    for (const atom of residue.atoms) add(residue, atom.name, atom.element, atom.xyz, "c");
  }
  return atoms.map((atom, index) => ({ ...atom, serial: index, index }));
}

/** The drug's atoms for 3Dmol, with the bonds and bond orders the complex lists. */
export function ligandAtoms(ligand: Complex["ligand"]): AtomSpec[] {
  const atoms: AtomSpec[] = ligand.atoms.map((atom, index) => ({
    ...point(atom.xyz),
    serial: index,
    index,
    elem: atom.element,
    atom: atom.name,
    resn: ligand.code,
    resi: ligand.number,
    chain: ligand.chain,
    hetflag: true,
    bonds: [],
    bondOrder: [],
  }));
  for (const bond of ligand.bonds) {
    const [a, b] = bond.atoms;
    const order = BOND_ORDER[bond.order];
    atoms[a].bonds!.push(b);
    atoms[a].bondOrder!.push(order);
    atoms[b].bonds!.push(a);
    atoms[b].bondOrder!.push(order);
  }
  return atoms;
}

/** The pocket residues, as a 3Dmol selection. */
export function pocketSelection(complex: Complex): AtomSelectionSpec {
  return { or: complex.pocket.map((residue) => ({ chain: residue.chain, resi: residue.number })) };
}

/** The hydrogen bonds, labelled like "Glu286". A bond whose residue atom isn't in the pocket is
 * left out rather than drawn to a wrong place. */
export function hydrogenBonds(complex: Complex): HydrogenBondLine[] {
  const pocket = new Map(complex.pocket.map((residue) => [residueKey(residue), residue]));
  return complex.contacts.flatMap((contact) => {
    if (contact.kind !== "hbond") return [];
    const residueAtom = pocket
      .get(residueKey(contact.residue))
      ?.atoms.find((atom) => atom.name === contact.residue_atom);
    const ligandAtom = complex.ligand.atoms[contact.ligand_atom];
    if (!residueAtom || !ligandAtom) return [];
    const { name, number, ins_code } = contact.residue;
    return [
      {
        label: `${name[0]}${name.slice(1).toLowerCase()}${number}${ins_code}`,
        residue: point(residueAtom.xyz),
        ligand: point(ligandAtom.xyz),
      },
    ];
  });
}

export function centroid(points: Point[]): Point {
  const sum = points.reduce((s, p) => ({ x: s.x + p.x, y: s.y + p.y, z: s.z + p.z }), {
    x: 0,
    y: 0,
    z: 0,
  });
  return { x: sum.x / points.length, y: sum.y / points.length, z: sum.z / points.length };
}

function unit(v: Point): Point {
  const length = Math.hypot(v.x, v.y, v.z) || 1;
  return { x: v.x / length, y: v.y / length, z: v.z / length };
}

/** Rotates `v` around the unit vector `axis` by `angle` radians (Rodrigues' formula). */
function rotate(v: Point, axis: Point, angle: number): Point {
  const cos = Math.cos(angle);
  const sin = Math.sin(angle);
  const dot = axis.x * v.x + axis.y * v.y + axis.z * v.z;
  return {
    x: v.x * cos + (axis.y * v.z - axis.z * v.y) * sin + axis.x * dot * (1 - cos),
    y: v.y * cos + (axis.z * v.x - axis.x * v.z) * sin + axis.y * dot * (1 - cos),
    z: v.z * cos + (axis.x * v.y - axis.y * v.x) * sin + axis.z * dot * (1 - cos),
  };
}

export function easeInOut(t: number): number {
  return t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2;
}

const DOCK_DISTANCE = 18;
const DOCK_TURN = 2.2;
const DOCK_AXIS = unit({ x: 0.3, y: 1, z: 0.2 });

/** The direction the drug comes in from: out of the pocket, away from the protein's middle. */
export function approachDirection(complex: Complex): Point {
  const drug = centroid(complex.ligand.atoms.map((atom) => point(atom.xyz)));
  const protein = centroid(complex.trace.map((residue) => point(residue.xyz)));
  return unit({ x: drug.x - protein.x, y: drug.y - protein.y, z: drug.z - protein.z });
}

/**
 * The drug's atoms part of the way into the pocket. At `progress` 0 it sits 18 Å out along
 * `approach`, turned away; at 1 it is in its bound pose. The path is an illustration; only the end
 * is from the structure.
 */
export function dockingPose(bound: Point[], approach: Point, progress: number): Point[] {
  const eased = easeInOut(progress);
  const distance = DOCK_DISTANCE * (1 - eased);
  const angle = DOCK_TURN * (1 - eased);
  const center = centroid(bound);
  return bound.map((p) => {
    const turned = rotate(
      { x: p.x - center.x, y: p.y - center.y, z: p.z - center.z },
      DOCK_AXIS,
      angle,
    );
    return {
      x: center.x + turned.x + approach.x * distance,
      y: center.y + turned.y + approach.y * distance,
      z: center.z + turned.z + approach.z * distance,
    };
  });
}
