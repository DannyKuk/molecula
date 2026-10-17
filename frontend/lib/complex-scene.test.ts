import { describe, expect, it } from "vitest";

import {
  approachDirection,
  assemblyDuration,
  assemblyFrame,
  assemblyOrder,
  centroid,
  dockingPose,
  hydrogenBonds,
  ligandAtoms,
  pocketSelection,
  proteinAtoms,
} from "./complex-scene";
import { SMALL_COMPLEX } from "./test-complexes";

describe("proteinAtoms", () => {
  const atoms = proteinAtoms(SMALL_COMPLEX);

  it("keeps one point per trace residue and every atom of the pocket residues instead", () => {
    expect(atoms.map((atom) => `${atom.chain}${atom.resi}${atom.icode}:${atom.atom}`)).toEqual([
      "A1:CA",
      "A2:CA",
      "A2:OE2",
      "B5:P",
      "A7A:OG1",
    ]);
    expect(atoms.map((atom) => atom.index)).toEqual([0, 1, 2, 3, 4]);
  });

  it("carries the secondary structure, with nucleotides and off-trace residues as coil", () => {
    expect(atoms.map((atom) => atom.ss)).toEqual(["h", "s", "s", "c", "c"]);
  });

  it("places the atoms at their coordinates", () => {
    expect(atoms[2]).toMatchObject({ x: 8, y: 0, z: 0, elem: "O", resn: "GLU", hetflag: false });
  });
});

describe("ligandAtoms", () => {
  it("lists every bond on both of its atoms with its order", () => {
    const atoms = ligandAtoms(SMALL_COMPLEX.ligand);

    expect(atoms.map((atom) => [atom.bonds, atom.bondOrder])).toEqual([
      [[1], [1.5]],
      [
        [0, 2],
        [1.5, 2],
      ],
      [[1], [2]],
    ]);
    expect(atoms[0]).toMatchObject({ elem: "N", resn: "LIG", hetflag: true, x: 10 });
  });
});

describe("pocketSelection", () => {
  it("selects the pocket residues by chain and number", () => {
    expect(pocketSelection(SMALL_COMPLEX)).toEqual({
      or: [
        { chain: "A", resi: 2 },
        { chain: "A", resi: 7 },
      ],
    });
  });
});

describe("hydrogenBonds", () => {
  it("draws each bond from the residue atom to the drug atom, labelled by residue", () => {
    expect(hydrogenBonds(SMALL_COMPLEX)).toEqual([
      { label: "Glu2", residue: { x: 8, y: 0, z: 0 }, ligand: { x: 10, y: 0, z: 0 } },
      { label: "Thr7A", residue: { x: 12, y: 3, z: 0 }, ligand: { x: 12, y: 0, z: 0 } },
    ]);
  });

  it("leaves out a bond to an atom the pocket doesn't have, and plain contacts", () => {
    const residueEnds = hydrogenBonds(SMALL_COMPLEX).map((bond) => bond.residue);

    expect(residueEnds).toHaveLength(2);
    expect(residueEnds).not.toContainEqual(expect.objectContaining({ x: 3.8 }));
  });
});

describe("dockingPose", () => {
  const bound = ligandAtoms(SMALL_COMPLEX.ligand).map(({ x, y, z }) => ({ x: x!, y: y!, z: z! }));
  const approach = approachDirection(SMALL_COMPLEX);

  it("ends in the bound pose", () => {
    dockingPose(bound, approach, 1).forEach((p, i) => {
      expect(p.x).toBeCloseTo(bound[i].x);
      expect(p.y).toBeCloseTo(bound[i].y);
      expect(p.z).toBeCloseTo(bound[i].z);
    });
  });

  it("starts 18 Å out along the approach, away from the protein, keeping the drug's shape", () => {
    const start = dockingPose(bound, approach, 0);
    const shift = { x: 18 * approach.x, y: 18 * approach.y, z: 18 * approach.z };
    const center = centroid(start);
    const boundCenter = centroid(bound);

    expect(center.x).toBeCloseTo(boundCenter.x + shift.x);
    expect(center.y).toBeCloseTo(boundCenter.y + shift.y);
    expect(center.z).toBeCloseTo(boundCenter.z + shift.z);
    expect(distance(start[0], start[2])).toBeCloseTo(distance(bound[0], bound[2]));
    expect(approach.x).toBeGreaterThan(0);
  });
});

function distance(a: { x: number; y: number; z: number }, b: { x: number; y: number; z: number }) {
  return Math.hypot(a.x - b.x, a.y - b.y, a.z - b.z);
}

describe("assemblyOrder", () => {
  it("grows the heavy atoms bond by bond from the first, then adds each hydrogen after its atom", () => {
    // C0 - C3 - O1, with H2 on O1 and H4 on C0.
    const atoms = [
      { elem: "C", bonds: [3, 4] },
      { elem: "O", bonds: [3, 2] },
      { elem: "H", bonds: [1] },
      { elem: "C", bonds: [0, 1] },
      { elem: "H", bonds: [0] },
    ];

    expect(assemblyOrder(atoms)).toEqual([0, 3, 1, 4, 2]);
  });

  it("builds a salt's separate parts one after the other", () => {
    const atoms = [
      { elem: "Na", bonds: [] },
      { elem: "C", bonds: [2] },
      { elem: "O", bonds: [1] },
    ];

    expect(assemblyOrder(atoms)).toEqual([0, 1, 2]);
  });
});

describe("assemblyFrame", () => {
  const order = [0, 3, 1];

  it("shows nothing before the first atom starts growing", () => {
    expect(assemblyFrame(order, -1)).toEqual({ bonded: [], growing: [] });
  });

  it("grows atoms one after another and gives an atom its bonds once it is full size", () => {
    const { bonded, growing } = assemblyFrame(order, 350);

    expect(bonded).toEqual([0]);
    expect(growing.map(({ atom }) => atom)).toEqual([3, 1]);
    expect(growing[0].scale).toBeGreaterThan(growing[1].scale);
  });

  it("has every atom bonded at the end", () => {
    expect(assemblyFrame(order, assemblyDuration(order.length))).toEqual({
      bonded: [0, 3, 1],
      growing: [],
    });
  });

  it("builds a large drug in about two seconds", () => {
    expect(assemblyDuration(52)).toBeLessThanOrEqual(2300);
    expect(assemblyDuration(0)).toBe(0);
  });
});
