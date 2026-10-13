import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { cardOf, type Card } from "@/lib/tool-cards";
import {
  ACETAMINOPHEN_NO_COMPLEX,
  COMPARISON_WITH_UNSUPPORTED,
  GLEEVEC_FOUND,
  GUAIFENESIN_TARGETS,
  IMATINIB_COMPLEX,
  IMATINIB_LABELS,
  METFORMIN_COMPLEX,
  METFORMIN_PROPERTIES,
  METFORMIN_TARGETS,
  ONE_DRUG_COMPARISON,
  TYLENOLL_NOT_SUPPORTED,
} from "@/lib/test-tool-results";

import { ToolCard } from "./tool-card";

type Args = Record<string, unknown>;

function renderCard(name: string, result: unknown, args: Args = {}, answer = "") {
  const card = cardOf({ id: "call_1", name, args, result }) as Exclude<Card, { kind: "pending" }>;
  render(<ToolCard text="Step" card={card} answer={answer} />);
  return screen.getByRole("button", { name: /^Step/ });
}

/** Opens the card and returns what it shows. */
function openCard(name: string, result: unknown, args: Args = {}, answer = "") {
  const trigger = renderCard(name, result, args, answer);
  fireEvent.click(trigger);
  return trigger.parentElement!;
}

function linkTo(card: HTMLElement, name: string | RegExp): string | null {
  return within(card).getByRole("link", { name }).getAttribute("href");
}

describe("ToolCard", () => {
  it("shows the step and a summary, and opens into the result", () => {
    const trigger = renderCard("resolve_drug", GLEEVEC_FOUND);

    expect(trigger.textContent).toBe("Step“Gleevec” → imatinib");
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText(/PubChem CID/)).toBeNull();

    fireEvent.click(trigger);

    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByText(/PubChem CID 5291/)).toBeDefined();
  });

  it("shows a name outside the store with the closest supported names", () => {
    const card = openCard("resolve_drug", TYLENOLL_NOT_SUPPORTED);

    expect(card.textContent).toContain("Not supported");
    expect(card.textContent).toContain("“Tylenoll” isn't in Molecula's data");
    expect(card.textContent).toContain("Closest supported names: Tylenol (acetaminophen)");
  });

  it("shows a rejected call with its problems", () => {
    const card = openCard("compare_drugs", ONE_DRUG_COMPARISON);

    expect(card.textContent).toContain("Rejected call");
    expect(within(card).getByRole("listitem").textContent).toBe(ONE_DRUG_COMPARISON.errors[0]);
  });
});

describe("resolve_drug", () => {
  it("says which name matched and links to PubChem", () => {
    const card = openCard("resolve_drug", GLEEVEC_FOUND);

    expect(card.textContent).toContain("“Gleevec” is a stored name for imatinib");
    expect(linkTo(card, "PubChem")).toBe(GLEEVEC_FOUND.source_url);
  });
});

describe("get_properties and compare_drugs", () => {
  it("lists one drug's properties with its PubChem page", () => {
    const card = openCard("get_properties", METFORMIN_PROPERTIES);

    expect(card.textContent).toContain("C4H11N5 · 129.16 g/mol");
    expect(within(card).getByRole("row", { name: /XLogP/ }).textContent).toContain("-1.3");
    expect(within(card).getByRole("row", { name: /Polar surface/ }).textContent).toContain(
      "91.5 Å²",
    );
    expect(linkTo(card, "PubChem")).toBe(METFORMIN_PROPERTIES.compound.source_url);
  });

  it("puts compared drugs side by side and marks a name outside the store", () => {
    const card = openCard("compare_drugs", COMPARISON_WITH_UNSUPPORTED);

    const headers = within(card)
      .getAllByRole("columnheader")
      .map((header) => header.textContent);
    expect(headers).toEqual(["ibuprofen", "naproxen", "Vicodinx not supported"]);
    expect(
      within(within(card).getByRole("row", { name: /Formula/ }))
        .getAllByRole("cell")
        .map((cell) => cell.textContent),
    ).toEqual(["C13H18O2", "C14H14O3", "–"]);
    expect(
      within(card)
        .getAllByRole("link")
        .map((link) => link.textContent),
    ).toEqual(["PubChem: ibuprofen", "PubChem: naproxen"]);
  });
});

describe("get_targets", () => {
  it("lists each target's mechanism and ChEMBL page, and folds long gene lists", () => {
    const card = openCard("get_targets", METFORMIN_TARGETS);
    const [complexI] = METFORMIN_TARGETS.targets;

    expect(card.textContent).toContain("2 targets");
    expect(card.textContent).toContain(complexI.mechanism);
    expect(within(card).getAllByRole("link", { name: "ChEMBL" })[0].getAttribute("href")).toBe(
      complexI.source_url,
    );
    expect(within(card).queryByText(complexI.gene_symbols[6])).toBeNull();

    fireEvent.click(within(card).getByRole("button", { name: "Show all 8" }));

    expect(within(card).getByText(complexI.gene_symbols[7])).toBeDefined();
  });

  it("says when ChEMBL lists no mechanism", () => {
    const card = openCard("get_targets", GUAIFENESIN_TARGETS);

    expect(card.textContent).toContain("No mechanism listed");
    expect(card.textContent).toContain("ChEMBL lists no mechanism of action for guaifenesin.");
  });
});

describe("get_complex", () => {
  it("shows the target, the hydrogen bonds and the closest residues of the complex", () => {
    const card = openCard("get_complex", IMATINIB_COMPLEX);

    expect(card.textContent).toContain("2HYY · ABL1 (BCR-ABL)");
    expect(linkTo(card, "PDB 2HYY")).toBe(IMATINIB_COMPLEX.source_url);
    expect(within(card).getAllByRole("row")).toHaveLength(1 + 6);
    expect(within(card).getByRole("row", { name: /ILE360/ }).textContent).toBe(
      "ILE360AO – N512.72 Å",
    );
    expect(within(card).getByRole("button", { name: "Show all 10" })).toBeDefined();
    expect(
      (within(card).getByRole("button", { name: "View in 3D" }) as HTMLButtonElement).disabled,
    ).toBe(true);
  });

  it("puts a stand-in structure's caption first and says when there are no hydrogen bonds", () => {
    const card = openCard("get_complex", METFORMIN_COMPLEX);

    expect(card.querySelector("p")?.textContent).toBe(METFORMIN_COMPLEX.caption);
    expect(card.textContent).toContain("No hydrogen bonds in this structure.");
  });

  it("says when a drug has no reviewed complex", () => {
    const card = openCard("get_complex", ACETAMINOPHEN_NO_COMPLEX);

    expect(card.textContent).toContain("No reviewed structure");
    expect(card.textContent).toContain("The 3D view shows the molecule alone.");
  });
});

describe("search_labels", () => {
  const args = { drug: "imatinib", section: "pharmacology" };

  it("says what it searched and lists the passages, marking the cited ones", () => {
    const card = openCard("search_labels", IMATINIB_LABELS, args, "Imatinib blocks BCR-ABL [1].");

    expect(card.textContent).toContain(
      `Searched for “${IMATINIB_LABELS.question}” in the imatinib label, pharmacology sections.`,
    );
    const passages = within(card).getAllByRole("listitem");
    expect(passages.map((passage) => passage.querySelector("summary")?.textContent)).toEqual([
      "[1] Gleevec · Mechanism of action · Jul 13, 2026cited",
      "[2] Gleevec · Pharmacokinetics · Jul 13, 2026",
    ]);
    expect(passages[0].textContent).toContain(IMATINIB_LABELS.passages[0].text);
    expect(linkTo(passages[0], "Open the label on DailyMed")).toBe(IMATINIB_LABELS.passages[0].url);
  });

  it("says when no passage matched and which drugs have no label", () => {
    const card = openCard("search_labels", {
      ...IMATINIB_LABELS,
      drugs_without_label: ["fluticasone"],
      unsupported: [TYLENOLL_NOT_SUPPORTED],
      passages: [],
    });

    expect(card.textContent).toContain("0 passages");
    expect(card.textContent).toContain("No US label for fluticasone.");
    expect(card.textContent).toContain("Not supported: Tylenoll.");
    expect(card.textContent).toContain("No passage matched the question.");
  });

  it("shows a search that named only drugs outside the store as not supported", () => {
    const card = openCard("search_labels", {
      status: "not_supported",
      question: "Is Tylenoll safe?",
      drugs: [TYLENOLL_NOT_SUPPORTED],
    });

    expect(card.textContent).toContain("“Tylenoll” isn't in Molecula's data");
  });
});
