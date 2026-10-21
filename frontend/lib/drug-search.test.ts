import { describe, expect, it } from "vitest";

import type { Compound, Drug, Resolution } from "./api";
import { byLetter, filterDrugs, namesToOffer } from "./drug-search";
import { notSupported } from "./test-fixtures";

const imatinib: Drug = {
  cid: 5291,
  name: "imatinib",
  aliases: ["Gleevec", "Glivec"],
  has_3d: true,
};
const acetaminophen: Drug = {
  cid: 1983,
  name: "acetaminophen",
  aliases: ["Tylenol", "Paracetamol"],
  has_3d: false,
};
const caffeine: Drug = { cid: 2519, name: "caffeine", aliases: [], has_3d: true };
const drugs = [acetaminophen, caffeine, imatinib];

describe("filterDrugs", () => {
  it("returns every drug for an empty or blank query", () => {
    expect(filterDrugs(drugs, "")).toEqual(drugs);
    expect(filterDrugs(drugs, "   ")).toEqual(drugs);
  });

  it("matches the generic name in any case", () => {
    expect(filterDrugs(drugs, "IMATINIB")).toEqual([imatinib]);
  });

  it("matches a brand or other alias in any case", () => {
    expect(filterDrugs(drugs, "tylenol")).toEqual([acetaminophen]);
    expect(filterDrugs(drugs, "PARACETAMOL")).toEqual([acetaminophen]);
  });

  it("matches part of a name and ignores surrounding spaces", () => {
    expect(filterDrugs(drugs, "  glee ")).toEqual([imatinib]);
  });

  it("returns nothing when no name or alias matches", () => {
    expect(filterDrugs(drugs, "aspirin")).toEqual([]);
  });
});

const imatinibCompound: Compound = {
  cid: 5291,
  name: "imatinib",
  inchikey: "KTUFNOKKBVMGRW-UHFFFAOYSA-N",
  smiles: "CC1=C(C=C(C=C1)NC(=O)C2=CC=C(C=C2)CN3CCN(CC3)C)NC4=NC=CC(=N4)C5=CN=CC=C5",
  formula: "C29H31N7O",
  molecular_weight: 493.6,
  xlogp: 3.5,
  tpsa: 86.3,
  hbond_donors: 2,
  hbond_acceptors: 7,
  rotatable_bonds: 7,
  heavy_atoms: 37,
  has_3d: true,
  conformer_source: "pubchem",
  source: "PubChem",
  source_url: "https://pubchem.ncbi.nlm.nih.gov/compound/5291",
};

describe("byLetter", () => {
  it("groups the drugs by the capital of their first letter, keeping their order", () => {
    const drug = (name: string): Drug => ({ cid: name.length, name, aliases: [], has_3d: true });

    const groups = byLetter([drug("acetaminophen"), drug("amlodipine"), drug("caffeine")]);

    expect(groups.map(({ letter, drugs }) => [letter, drugs.map(({ name }) => name)])).toEqual([
      ["A", ["acetaminophen", "amlodipine"]],
      ["C", ["caffeine"]],
    ]);
  });

  it("gives no groups for no drugs", () => {
    expect(byLetter([])).toEqual([]);
  });
});

describe("namesToOffer", () => {
  it("offers the backend's suggestions for an unsupported name, in its order", () => {
    const suggestions = [
      { alias: "Gleevec", cid: 5291, name: "imatinib" },
      { alias: "Glivec", cid: 5291, name: "imatinib" },
    ];

    expect(namesToOffer(notSupported("Gleevek", suggestions))).toEqual(suggestions);
  });

  it("offers nothing when the backend has no close name", () => {
    expect(namesToOffer(notSupported("aspirin", []))).toEqual([]);
  });

  it("offers the drug a salt name or synonym resolves to", () => {
    const resolution: Resolution = {
      query: "imatinib mesylate",
      status: "found",
      compound: imatinibCompound,
      matched_alias: "imatinib",
      match_kind: "name",
      suggestions: [],
    };

    expect(namesToOffer(resolution)).toEqual([{ alias: "imatinib", cid: 5291, name: "imatinib" }]);
  });
});
