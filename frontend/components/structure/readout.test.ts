import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import type { Atom, Complex, Molecule } from "@/lib/api";
import imatinib from "@/lib/fixtures/complex-5291.json";
import { SMALL_COMPLEX } from "@/lib/test-complexes";

import { ELEMENT_NAMES, legendElements, readout } from "./readout";
import { COLORS, type SceneData } from "./scene";

const acetaminophen = readFileSync(
  path.join(__dirname, "../../lib/fixtures/structure-1983.sdf"),
  "utf8",
);

describe("readout", () => {
  it("counts the drug's atoms, the residues within 4 Å and the hydrogen bonds of a complex", () => {
    expect(readout({ kind: "complex", complex: imatinib as unknown as Complex })).toEqual([
      "37 atoms",
      "23 residues",
      "6 H-bonds",
    ]);
  });

  it("counts a single residue or hydrogen bond in the singular", () => {
    const complex = {
      ...SMALL_COMPLEX,
      pocket: SMALL_COMPLEX.pocket.slice(0, 1),
      contacts: SMALL_COMPLEX.contacts.filter((contact) => contact.kind === "hbond").slice(0, 1),
    };

    expect(readout({ kind: "complex", complex })).toEqual(["3 atoms", "1 residue", "1 H-bond"]);
  });

  it("counts only the atoms of a molecule without a complex, leaving out its hydrogens", () => {
    expect(readout({ kind: "molecule", sdf: acetaminophen })).toEqual(["11 atoms"]);
  });

  it("shows nothing for a molecule file it can't read", () => {
    expect(readout({ kind: "molecule", sdf: "1983\n$$$$\n" })).toEqual([]);
  });
});

describe("legendElements", () => {
  const complex = { kind: "complex", complex: imatinib as unknown as Complex } as const;

  it("lists the elements the view draws besides carbon: the drug's, and the pocket's outside Molecule view", () => {
    expect(legendElements(complex, "molecule")).toEqual(["N", "O"]);
    expect(legendElements(complex, "site")).toEqual(["N", "O", "S"]);
    expect(legendElements(complex, "protein")).toEqual(["N", "O", "S"]);
  });

  it("lists a drug's chlorine, fluorine and iodine and a nucleotide's phosphorus, but not a cofactor's", () => {
    const halogens: Atom[] = [
      { name: "CL1", element: "Cl", xyz: [13, 0, 0] },
      { name: "F1", element: "F", xyz: [14, 0, 0] },
      { name: "I1", element: "I", xyz: [15, 0, 0] },
    ];
    const nucleotide: Complex["pocket"][number] = {
      chain: "B",
      number: 5,
      ins_code: "",
      name: "DA",
      atoms: [{ name: "P", element: "P", xyz: [0, 6, 0] }],
    };
    const cofactor: Molecule = {
      code: "ATP",
      chain: "A",
      number: 601,
      atoms: [{ name: "PA", element: "P", xyz: [20, 0, 0] }],
      bonds: [],
    };
    const data: SceneData = {
      kind: "complex",
      complex: {
        ...SMALL_COMPLEX,
        ligand: { ...SMALL_COMPLEX.ligand, atoms: [...SMALL_COMPLEX.ligand.atoms, ...halogens] },
        pocket: [...SMALL_COMPLEX.pocket, nucleotide],
        cofactors: [cofactor],
      },
    };

    expect(legendElements(data, "molecule")).toEqual(["Cl", "F", "I", "N", "O"]);
    expect(legendElements(data, "site")).toEqual(["Cl", "F", "I", "N", "O", "P"]);
  });

  it("lists the hydrogens of a molecule without a complex, and nothing for a file it can't read", () => {
    expect(legendElements({ kind: "molecule", sdf: acetaminophen }, "molecule")).toEqual([
      "H",
      "N",
      "O",
    ]);
    expect(legendElements({ kind: "molecule", sdf: "1983\n$$$$\n" }, "molecule")).toEqual([]);
  });
});

describe("ELEMENT_NAMES", () => {
  it("has a colour for every element it names, on the screen and on paper", () => {
    for (const colors of [COLORS.screen, COLORS.screenDark, COLORS.paper]) {
      expect(Object.keys(colors.elements).sort()).toEqual(Object.keys(ELEMENT_NAMES).sort());
    }
  });
});
