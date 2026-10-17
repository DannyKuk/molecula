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

type BondedAtom = { elem?: string; bonds?: number[] };

/**
 * The order the drug's atoms appear in: the heavy atoms bond by bond from the first one, so the drug
 * grows as one piece, then each hydrogen in the order of the atom it sits on.
 */
export function assemblyOrder(atoms: BondedAtom[]): number[] {
  const heavy = (i: number) => atoms[i].elem !== "H";
  const order: number[] = [];
  const seen = new Set<number>();
  for (let first = 0; first < atoms.length; first++) {
    if (seen.has(first) || !heavy(first)) continue;
    const queue = [first];
    seen.add(first);
    while (queue.length > 0) {
      const atom = queue.shift()!;
      order.push(atom);
      for (const next of atoms[atom].bonds ?? []) {
        if (!seen.has(next) && heavy(next)) {
          seen.add(next);
          queue.push(next);
        }
      }
    }
  }
  const place = new Map(order.map((atom, i) => [atom, i]));
  const hydrogens = atoms.flatMap((_, i) => (heavy(i) ? [] : [i]));
  const carrier = (i: number) => place.get(atoms[i].bonds?.[0] ?? -1) ?? order.length;
  return [...order, ...hydrogens.sort((a, b) => carrier(a) - carrier(b))];
}

const ASSEMBLY_MS = 2000;
const ATOM_STEP_MS = 90;
const POP_MS = 300;

/** How long the drug takes to build itself up. */
export function assemblyDuration(atomCount: number): number {
  return atomCount === 0 ? 0 : (atomCount - 1) * atomStep(atomCount) + POP_MS;
}

function atomStep(atomCount: number): number {
  return Math.min(ATOM_STEP_MS, ASSEMBLY_MS / atomCount);
}

/**
 * The drug `elapsed` ms into building itself up: the atoms that are full size and drawn with their
 * bonds, and the ones still growing, with their size from 0 to 1. 3Dmol draws a bond only when both
 * atoms have sticks, so a bond appears once its later atom is full size.
 */
export function assemblyFrame(
  order: number[],
  elapsed: number,
): { bonded: number[]; growing: { atom: number; scale: number }[] } {
  const step = atomStep(order.length);
  const bonded: number[] = [];
  const growing: { atom: number; scale: number }[] = [];
  order.forEach((atom, i) => {
    const since = elapsed - i * step;
    if (since >= POP_MS) bonded.push(atom);
    else if (since > 0) growing.push({ atom, scale: easeOut(since / POP_MS) });
  });
  return { bonded, growing };
}

function easeOut(t: number): number {
  return 1 - (1 - t) ** 3;
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
