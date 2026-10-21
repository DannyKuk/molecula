import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { startTurn, type Turn } from "@/lib/chat-turn";
import { CHECKING_ANSWER } from "@/lib/source-check";
import { IMATINIB_LABELS, IMATINIB_TRACE } from "@/lib/test-tool-results";

import { FlowTab } from "./flow-tab";

const SEARCHED: Turn = {
  ...startTurn("How does imatinib work?"),
  state: "done",
  category: "ok",
  answer: "Imatinib blocks BCR-ABL [1].",
  steps: [
    { text: "Checking the question" },
    {
      text: "Searching the Gleevec label",
      tool: {
        id: "call_1",
        name: "search_labels",
        args: { question: IMATINIB_LABELS.question, drug: "Gleevec", section: "pharmacology" },
        result: IMATINIB_LABELS,
        trace: IMATINIB_TRACE,
      },
    },
    { text: CHECKING_ANSWER },
  ],
  sourceCheck: { checked: true, claims: [] },
};

function stepItem(title: string): HTMLElement {
  const heading = screen.getByRole("heading", { name: (name) => name.includes(title) });
  return heading.closest("li") as HTMLElement;
}

describe("FlowTab", () => {
  it("tags every step with who did it and links it to the guide", () => {
    render(<FlowTab turn={SEARCHED} />);

    expect(within(stepItem("Check the question")).getByText("Jev or chat model")).toBeDefined();
    expect(within(stepItem("Score the passages")).getByText("Embedder")).toBeDefined();
    expect(within(stepItem("keep the top 2")).getByText("Code")).toBeDefined();
    expect(
      within(stepItem("Decide what to look up"))
        .getByRole("link", { name: "What this step means" })
        .getAttribute("href"),
    ).toBe("/how-it-answers#decide-what-to-look-up");
    expect(screen.getAllByRole("link", { name: "What this step means" })).toHaveLength(8);
    expect(screen.getByRole("link", { name: "How Molecula answers" }).getAttribute("href")).toBe(
      "/how-it-answers",
    );
  });

  it("groups the search's steps under the line that announced it, with its call and bars", () => {
    render(<FlowTab turn={SEARCHED} />);

    const search = screen.getByRole("list", { name: "Searching the Gleevec label" });
    expect(
      within(search).getByText('search_labels(drug="Gleevec", section="pharmacology")'),
    ).toBeDefined();
    expect(search.children).toHaveLength(4);
    expect(
      within(stepItem("keep the top 2")).getByRole("list", { name: "Passages by score" }),
    ).toBeDefined();
  });

  it("marks the lookup steps skipped when the answer looked nothing up", () => {
    render(
      <FlowTab
        turn={{
          ...SEARCHED,
          steps: [{ text: "Checking the question" }, { text: CHECKING_ANSWER }],
          answer: "Hello! Ask me about a medicine.",
        }}
      />,
    );

    const narrow = stepItem("Narrow the search to the drug");
    expect(within(narrow).getByText("Skipped")).toBeDefined();
    expect(within(stepItem("Decide what to look up")).getByText("Skipped")).toBeDefined();
    expect(screen.getByText("The chat model answered without looking anything up.")).toBeDefined();
  });

  it("marks the running step and the steps still to come on a live answer", () => {
    render(
      <FlowTab
        turn={{
          ...startTurn("How does imatinib work?"),
          steps: [{ text: "Checking the question" }],
        }}
      />,
    );

    expect(within(stepItem("Check the question")).getByText("Running")).toBeDefined();
    expect(within(stepItem("Write the answer")).getByText("Not yet")).toBeDefined();
  });
});
