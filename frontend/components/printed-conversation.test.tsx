import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Source } from "@/lib/chat";
import { startTurn, type Turn } from "@/lib/chat-turn";
import { IMATINIB_SOURCES } from "@/lib/test-fixtures";

import { askedTime, PrintedEnd, PrintedHeader, PrintedSources } from "./printed-conversation";

const PDE5A: Source = {
  kind: "chembl",
  name: "cGMP-specific 3',5'-cyclic phosphodiesterase",
  url: "https://www.ebi.ac.uk/chembl/explore/target/CHEMBL1827",
  section: null,
  effective_time: null,
  ref: 1,
};

function answered(sources: Source[] | null): Turn {
  return {
    ...startTurn("How does Gleevec work?"),
    state: "done",
    answer: "It blocks BCR-ABL.",
    sources,
  };
}

function credit(): HTMLElement | null {
  return screen.queryByText(/^Data provided by the U\.S\. Food and Drug Administration/);
}

describe("PrintedHeader", () => {
  it("counts the questions, on paper only", () => {
    const { rerender } = render(
      <PrintedHeader title="How does Gleevec work?" questions={["How does Gleevec work?"]} />,
    );

    const printed = screen.getByRole("region", { name: "Printed conversation" });
    expect(printed.className).toContain("hidden");
    expect(printed.className).toContain("print:block");
    expect(within(printed).getByText(/^1 question · Printed on/)).toBeDefined();

    rerender(<PrintedHeader title="How does Gleevec work?" questions={["A?", "B?", "C?"]} />);
    expect(within(printed).getByText(/^3 questions · Printed on/)).toBeDefined();
  });

  it("prints a renamed chat's title, but not a title that repeats the first question", () => {
    const { rerender } = render(
      <PrintedHeader title="How does Gleevec work?" questions={["How does Gleevec work?"]} />,
    );
    expect(screen.queryByRole("heading")).toBeNull();

    rerender(<PrintedHeader title="Gleevec for my aunt" questions={["How does Gleevec work?"]} />);
    expect(screen.getByRole("heading", { name: "Gleevec for my aunt" })).toBeDefined();
  });
});

describe("PrintedSources", () => {
  it("prints every source with the numbers the answer cites it with, and its link", () => {
    render(<PrintedSources sources={IMATINIB_SOURCES} />);

    const lines = screen.getAllByRole("listitem");
    expect(lines.map((line) => line.firstChild?.textContent)).toEqual(["[1]", "[2, 3]", "[4]"]);
    expect(lines[1].textContent).toContain("Gleevec – Pharmacokinetics");
    expect(within(lines[1]).getByText(IMATINIB_SOURCES[1].url)).toBeDefined();
    expect(lines[2].textContent).toContain("PubChem – imatinib");
  });

  it("leaves the number out for a source the answer can't cite", () => {
    render(<PrintedSources sources={[{ ...PDE5A, ref: null }]} />);

    expect(screen.getByRole("listitem").firstChild?.textContent).toBe("");
  });

  it("prints nothing for an answer without sources", () => {
    const { container } = render(<PrintedSources sources={[]} />);

    expect(container.innerHTML).toBe("");
  });
});

describe("PrintedEnd", () => {
  it("ends with the disclaimer and one openFDA credit when answers used label text", () => {
    render(<PrintedEnd turns={[answered(IMATINIB_SOURCES), answered(IMATINIB_SOURCES)]} />);

    const end = screen.getByRole("region", { name: "End of the printed conversation" });
    expect(within(end).getByText(/Molecula is an AI assistant/)).toBeDefined();
    expect(within(end).getAllByText(/^Data provided by the U\.S\. Food/)).toHaveLength(1);
  });

  it("gives no openFDA credit without label text", () => {
    render(<PrintedEnd turns={[answered([PDE5A]), answered(null)]} />);

    expect(credit()).toBeNull();
  });
});

describe("askedTime", () => {
  it("gives the day and the time on a 24-hour clock", () => {
    expect(askedTime(new Date(2026, 9, 20, 14, 5).getTime())).toBe("Oct 20, 2026, 14:05");
  });
});
