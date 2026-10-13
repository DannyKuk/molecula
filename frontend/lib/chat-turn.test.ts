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

  it("takes passages from label search results only", () => {
    const turn = startTurn("What does sildenafil bind to?");

    expect(
      applyEvent(turn, toolResult("get_targets", { passages: [IMATINIB_PASSAGES[1]] })).passages,
    ).toEqual({});
    expect(
      applyEvent(turn, toolResult("search_labels", { status: "not_supported" })).passages,
    ).toEqual({});
    expect(
      applyEvent(turn, toolResult("search_labels", { passages: [{ ref: "1" }, null] })).passages,
    ).toEqual({});
  });

  it("gives each step the tool call it announced and, once it returns, the result", () => {
    const steps = [
      { type: "status" as const, message: "Checking the question" },
      { type: "status" as const, message: "Looking up Gleevec" },
      { type: "tool_call" as const, id: "call_1", name: "resolve_drug", args: { name: "Gleevec" } },
      { type: "status" as const, message: "Finding the targets of imatinib" },
      { type: "tool_call" as const, id: "call_2", name: "get_targets", args: { drug: "imatinib" } },
      toolResult("resolve_drug", { status: "found" }),
    ].reduce(applyEvent, startTurn("What does Gleevec bind to?")).steps;

    expect(steps).toEqual([
      { text: "Checking the question" },
      {
        text: "Looking up Gleevec",
        tool: {
          id: "call_1",
          name: "resolve_drug",
          args: { name: "Gleevec" },
          result: { status: "found" },
        },
      },
      {
        text: "Finding the targets of imatinib",
        tool: { id: "call_2", name: "get_targets", args: { drug: "imatinib" } },
      },
    ]);
  });

  it("ignores a tool call without its step and a result without its call", () => {
    const announced = [
      { type: "status" as const, message: "Looking up Gleevec" },
      { type: "tool_call" as const, id: "call_1", name: "resolve_drug", args: {} },
    ].reduce(applyEvent, startTurn("What is Gleevec?"));

    const turn = [
      { type: "tool_call" as const, id: "call_2", name: "get_targets", args: {} },
      { ...toolResult("get_targets", {}), id: "call_9" },
    ].reduce(applyEvent, announced);

    expect(turn.steps).toEqual(announced.steps);
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
