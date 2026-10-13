import { describe, expect, it } from "vitest";

import { applyEvent, startTurn } from "./chat-turn";
import { IMATINIB_PASSAGES, IMATINIB_SOURCES, OPENFDA_DISCLAIMER } from "./test-fixtures";

function toolResult(name: string, result: unknown) {
  return { type: "tool_result" as const, id: "call_1", name, status: "found", result };
}

describe("applyEvent", () => {
  it("keeps the label search's passages by the number the answer cites them with", () => {
    const passages = Object.values(IMATINIB_PASSAGES).map((passage) => ({
      ...passage,
      section: "mechanism_of_action",
      score: 0.6,
    }));

    const turn = applyEvent(
      startTurn("How does imatinib work?"),
      toolResult("search_labels", { passages }),
    );

    expect(turn.passages).toEqual(IMATINIB_PASSAGES);
  });

  it("adds the passages of a second label search to the first's", () => {
    const first = applyEvent(
      startTurn("Compare"),
      toolResult("search_labels", { passages: [IMATINIB_PASSAGES[1]] }),
    );

    const turn = applyEvent(
      first,
      toolResult("search_labels", { passages: [IMATINIB_PASSAGES[2]] }),
    );

    expect(Object.keys(turn.passages)).toEqual(["1", "2"]);
  });

  it("ignores other tools and label search results without passages", () => {
    const turn = startTurn("What does sildenafil bind to?");

    expect(applyEvent(turn, toolResult("get_targets", { passages: [IMATINIB_PASSAGES[1]] }))).toBe(
      turn,
    );
    expect(
      applyEvent(turn, toolResult("search_labels", { status: "not_supported" })).passages,
    ).toEqual({});
    expect(
      applyEvent(turn, toolResult("search_labels", { passages: [{ ref: "1" }, null] })).passages,
    ).toEqual({});
  });

  it("keeps the sources and the disclaimer when they arrive", () => {
    const turn = applyEvent(startTurn("How does imatinib work?"), {
      type: "sources",
      sources: IMATINIB_SOURCES,
      unknown_refs: [],
      disclaimer: OPENFDA_DISCLAIMER,
    });

    expect(turn.sources).toEqual(IMATINIB_SOURCES);
    expect(turn.disclaimer).toBe(OPENFDA_DISCLAIMER);
  });

  it("has no sources while the answer streams", () => {
    expect(startTurn("How does imatinib work?").sources).toBeNull();
  });
});
