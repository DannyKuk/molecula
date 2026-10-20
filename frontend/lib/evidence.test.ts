import { describe, expect, it } from "vitest";

import type { Source } from "./chat";
import { startTurn } from "./chat-turn";
import { defaultTab, sourceCards } from "./evidence";
import { IMATINIB_SOURCES } from "./test-fixtures";
import { IMATINIB_COMPLEX } from "./test-tool-results";

const PUBCHEM = IMATINIB_SOURCES[3];

describe("sourceCards", () => {
  it("lists each passage on its own and each page once with all its numbers, in order", () => {
    const again: Source = { ...PUBCHEM, ref: 6 };
    const unnumbered: Source = {
      ...PUBCHEM,
      url: "https://www.rcsb.org/structure/2HYY",
      ref: null,
    };

    const cards = sourceCards([unnumbered, again, ...IMATINIB_SOURCES]);

    expect(cards.map((card) => card.refs)).toEqual([[1], [2], [3], [4, 6], []]);
    expect(cards[3].source.url).toBe(PUBCHEM.url);
  });
});

describe("defaultTab", () => {
  const imatinibIn3D = {
    text: "Getting the complex of imatinib",
    tool: { id: "call_1", name: "get_complex", args: {}, result: IMATINIB_COMPLEX },
  };

  it("opens an answer that is coming in on its steps", () => {
    expect(defaultTab({ ...startTurn("q"), steps: [imatinibIn3D] })).toBe("steps");
  });

  it("opens a finished answer on its 3D view, or on its sources without one", () => {
    const done = { ...startTurn("q"), state: "done" as const };
    expect(defaultTab({ ...done, steps: [imatinibIn3D] })).toBe("3d");
    expect(defaultTab(done)).toBe("sources");
  });
});
