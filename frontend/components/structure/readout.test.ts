import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it } from "vitest";

import type { Complex } from "@/lib/api";
import imatinib from "@/lib/fixtures/complex-5291.json";
import { SMALL_COMPLEX } from "@/lib/test-complexes";

import { readout } from "./readout";

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
