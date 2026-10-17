import { describe, expect, it } from "vitest";

import {
  citedRefs,
  citedSources,
  CITATION_RUN,
  runRefs,
  sectionName,
  sourceLabel,
  sourceLines,
} from "./citations";
import { IMATINIB_SOURCES } from "./test-fixtures";

function runs(text: string): string[] {
  return text.match(CITATION_RUN) ?? [];
}

describe("citations", () => {
  it("reads every way the models write a citation, as the backend does", () => {
    const answer = "A [1]. B [2][3]. C [4, 5]. D 【6】. E [7] 【8】.";

    expect(runs(answer)).toEqual(["[1]", "[2][3]", "[4, 5]", "【6】", "[7] 【8】"]);
    expect(citedRefs(answer)).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
  });

  it("counts a number once, in the order it is first cited", () => {
    expect(citedRefs("A [2][1]. B [1, 2]. C [3].")).toEqual([2, 1, 3]);
    expect(runRefs("[3, 3][3]")).toEqual([3]);
  });

  it("doesn't take Markdown links or plain brackets for citations", () => {
    expect(citedRefs("See [DailyMed](https://dailymed.nlm.nih.gov/) and [note] or [1a].")).toEqual(
      [],
    );
  });

  it("keeps the label sources a run cites and leaves out numbers that point at nothing", () => {
    const cited = citedSources([2, 9, 1], IMATINIB_SOURCES);

    expect(cited.map((source) => source.ref)).toEqual([2, 1]);
    expect(cited.map(sourceLabel)).toEqual([
      "Gleevec · Pharmacokinetics",
      "Gleevec · Mechanism of action",
    ]);
  });

  it("names a page by its site and entry", () => {
    expect(sourceLabel(IMATINIB_SOURCES[3])).toBe("PubChem · imatinib");
    expect(sourceLabel({ ...IMATINIB_SOURCES[3], kind: "rcsb", name: "2HYY" })).toBe(
      "RCSB PDB · 2HYY",
    );
  });

  it("names label sections as words", () => {
    expect(sectionName("ask_doctor_or_pharmacist")).toBe("Ask doctor or pharmacist");
    expect(sectionName(null)).toBe("Label");
  });
});

describe("sourceLines", () => {
  it("names a label passage by drug and section and a page by its site, after its numbers", () => {
    expect(sourceLines(IMATINIB_SOURCES)).toEqual([
      `[1] Gleevec – Mechanism of action – ${IMATINIB_SOURCES[0].url}`,
      `[2, 3] Gleevec – Pharmacokinetics – ${IMATINIB_SOURCES[1].url}`,
      "[4] PubChem – imatinib – https://pubchem.ncbi.nlm.nih.gov/compound/5291",
    ]);
  });

  it("leaves out the number of a source the answer can't cite", () => {
    expect(sourceLines([{ ...IMATINIB_SOURCES[3], ref: null }])).toEqual([
      "PubChem – imatinib – https://pubchem.ncbi.nlm.nih.gov/compound/5291",
    ]);
  });
});
