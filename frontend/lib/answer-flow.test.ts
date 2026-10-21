import { describe, expect, it } from "vitest";

import { boostedRanking, EXAMPLE_PASSAGES, FLOW_STEPS, SECTION_BOOST } from "./answer-flow";

describe("boostedRanking", () => {
  it("moves the passages in the section asked for up by the bonus", () => {
    const ranked = boostedRanking(EXAMPLE_PASSAGES, SECTION_BOOST);

    expect(ranked.map(({ section, before, after }) => [section, before, after])).toEqual([
      ["Drug interactions", 4, 1],
      ["Drug and/or lab test interactions", 5, 2],
      ["Nursing mothers", 1, 3],
      ["Precautions", 2, 4],
      ["Nursing mothers", 3, 5],
    ]);
    expect(ranked[0].score).toBeCloseTo(0.67);
  });

  it("keeps the order by similarity when nothing is in the section", () => {
    const ranked = boostedRanking(
      [
        { section: "Warnings", similarity: 0.5, inSection: false },
        { section: "Dosage", similarity: 0.7, inSection: false },
      ],
      SECTION_BOOST,
    );

    expect(ranked.map(({ section, before, after }) => [section, before, after])).toEqual([
      ["Dosage", 1, 1],
      ["Warnings", 2, 2],
    ]);
  });

  it("keeps the given order for equal scores", () => {
    const ranked = boostedRanking(
      [
        { section: "First", similarity: 0.6, inSection: false },
        { section: "Second", similarity: 0.6, inSection: false },
      ],
      SECTION_BOOST,
    );

    expect(ranked.map(({ section }) => section)).toEqual(["First", "Second"]);
  });

  it("is empty for a search that kept nothing", () => {
    expect(boostedRanking([], SECTION_BOOST)).toEqual([]);
  });
});

describe("FLOW_STEPS", () => {
  it("gives every step its own anchor", () => {
    const ids = FLOW_STEPS.map(({ id }) => id);

    expect(new Set(ids).size).toBe(ids.length);
  });
});
