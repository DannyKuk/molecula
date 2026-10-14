import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Citations } from "@/lib/citations";
import { IMATINIB_PASSAGES, IMATINIB_SOURCES } from "@/lib/test-fixtures";

import { AnswerMarkdown } from "./answer-markdown";

const CITATIONS: Citations = { sources: IMATINIB_SOURCES, passages: IMATINIB_PASSAGES };

function renderAnswer(text: string, citations: Citations | null = CITATIONS) {
  return render(<AnswerMarkdown text={text} citations={citations} />);
}

function chips(): string[] {
  return screen.queryAllByRole("button").map((chip) => chip.textContent ?? "");
}

async function openChip(name: string | RegExp) {
  fireEvent.click(screen.getByRole("button", { name }));
  return within(await screen.findByRole("dialog"));
}

describe("CitationChip", () => {
  it("shows a cited passage as a chip naming the label and its section", () => {
    const { container } = renderAnswer("Imatinib blocks BCR-ABL [1].");

    expect(chips()).toEqual(["Gleevec · Mechanism of action"]);
    expect(container.textContent).toBe("Imatinib blocks BCR-ABL Gleevec · Mechanism of action.");
  });

  it("opens the passage, the label date and the DailyMed link from the chip", async () => {
    renderAnswer("Imatinib blocks BCR-ABL [1].");

    const popover = await openChip("Sources: Gleevec · Mechanism of action");

    expect(popover.getByText(/inhibits the BCR-ABL tyrosine kinase/)).toBeDefined();
    expect(popover.getByText("FDA label of Jul 13, 2026")).toBeDefined();
    const link = popover.getByRole("link", { name: "Open the label on DailyMed" });
    expect(link.getAttribute("href")).toBe(IMATINIB_SOURCES[0].url);
    expect(link.getAttribute("target")).toBe("_blank");
    expect(link.getAttribute("rel")).toBe("noopener noreferrer");
  });

  it("joins citations written next to each other into one chip that names each section once", async () => {
    renderAnswer(
      "It is cleared by the liver [2][3]. It blocks BCR-ABL and is absorbed well [1, 2].",
    );

    expect(chips()).toEqual(["Gleevec · Pharmacokinetics", "Gleevec · Mechanism of action +1"]);

    const popover = await openChip("Sources: Gleevec · Pharmacokinetics");
    expect(popover.getAllByRole("listitem")).toHaveLength(2);
    expect(popover.getByText(/25% of the dose/)).toBeDefined();
    expect(popover.getByText(/have been evaluated/)).toBeDefined();
  });

  it("shows a cited PubChem page as a chip naming the site and the compound", async () => {
    renderAnswer("Imatinib weighs 493.6 g/mol [4].");

    expect(chips()).toEqual(["PubChem · imatinib"]);
    const popover = await openChip("Sources: PubChem · imatinib");
    expect(popover.getAllByRole("listitem")[0].textContent).toBe(
      "PubChem · imatinibOpen on PubChem",
    );
    const link = popover.getByRole("link", { name: "Open on PubChem" });
    expect(link.getAttribute("href")).toBe("https://pubchem.ncbi.nlm.nih.gov/compound/5291");
    expect(link.getAttribute("target")).toBe("_blank");
  });

  it("joins a label passage and a page cited together into one chip", async () => {
    renderAnswer("Imatinib blocks BCR-ABL and weighs 493.6 g/mol [1][4].");

    expect(chips()).toEqual(["Gleevec · Mechanism of action +1"]);
    const popover = await openChip(/Sources/);
    expect(popover.getByRole("link", { name: "Open the label on DailyMed" })).toBeDefined();
    expect(popover.getByRole("link", { name: "Open on PubChem" })).toBeDefined();
  });

  it("reads gpt-oss's own brackets like the others", () => {
    renderAnswer("Imatinib blocks BCR-ABL【1】.");

    expect(chips()).toEqual(["Gleevec · Mechanism of action"]);
  });

  it("leaves out a citation that points at no passage, and keeps the ones beside it", () => {
    const { container } = renderAnswer(
      "Sildenafil binds PDE5A【9】. Imatinib blocks BCR-ABL [9][1].",
    );

    expect(chips()).toEqual(["Gleevec · Mechanism of action"]);
    expect(container.textContent).toBe(
      "Sildenafil binds PDE5A. Imatinib blocks BCR-ABL Gleevec · Mechanism of action.",
    );
  });

  it("leaves every citation out of an answer without sources", () => {
    const { container } = renderAnswer("Molecula only answers questions about medicines [1].", {
      sources: [],
      passages: {},
    });

    expect(chips()).toEqual([]);
    expect(container.textContent).toBe("Molecula only answers questions about medicines.");
  });

  it("keeps citations as written while the answer is still streaming", () => {
    const { container } = renderAnswer("Imatinib blocks BCR-ABL [1][2] and 【3】", null);

    expect(chips()).toEqual([]);
    expect(container.textContent).toBe("Imatinib blocks BCR-ABL [1][2] and 【3】");
  });

  it("leaves citations in code as they are", () => {
    const { container } = renderAnswer("The pattern `[1]` stands for a citation [1].");

    expect(container.querySelector("code")?.textContent).toBe("[1]");
    expect(chips()).toEqual(["Gleevec · Mechanism of action"]);
  });

  it("shows a chip without an excerpt when the passage text is missing", async () => {
    renderAnswer("Imatinib blocks BCR-ABL [1].", { sources: IMATINIB_SOURCES, passages: {} });

    const popover = await openChip(/Sources/);

    await waitFor(() => expect(popover.getByRole("link")).toBeDefined());
    expect(popover.getAllByRole("listitem")[0].textContent).toBe(
      "Gleevec · Mechanism of actionFDA label of Jul 13, 2026Open the label on DailyMed",
    );
  });
});
