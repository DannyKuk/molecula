import { describe, expect, it } from "vitest";

import type { Drug } from "./api";
import { filterDrugs } from "./drug-search";

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
