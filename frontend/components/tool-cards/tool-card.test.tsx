import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LANGUAGE_KEY } from "@/lib/language";
import { cardOf, type Card, type RetrievalTrace } from "@/lib/tool-cards";
import {
  ACETAMINOPHEN_NO_COMPLEX,
  COMPARISON_WITH_UNSUPPORTED,
  GLEEVEC_FOUND,
  GUAIFENESIN_TARGETS,
  IMATINIB_COMPLEX,
  IMATINIB_LABELS,
  IMATINIB_TRACE,
  METFORMIN_COMPLEX,
  METFORMIN_PROPERTIES,
  METFORMIN_TARGETS,
  ONE_DRUG_COMPARISON,
  TYLENOLL_NOT_SUPPORTED,
} from "@/lib/test-tool-results";

import { ToolCard } from "./tool-card";
import { ShowStructure } from "./view-in-3d";

type Args = Record<string, unknown>;

function renderCard(name: string, result: unknown, args: Args = {}, answer = "") {
  const card = cardOf({ id: "call_1", name, args, result }) as Exclude<Card, { kind: "pending" }>;
  render(<ToolCard text="Step" card={card} answer={answer} current={false} />);
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
  });

  it("opens the drug's 3D view in the evidence panel", () => {
    const card = cardOf({ id: "call_1", name: "get_complex", args: {}, result: IMATINIB_COMPLEX });
    const show = vi.fn();
    render(
      <ShowStructure value={show}>
        <ToolCard
          text="Step"
          card={card as Exclude<Card, { kind: "pending" }>}
          answer=""
          current={false}
        />
      </ShowStructure>,
    );

    fireEvent.click(screen.getByRole("button", { name: /^Step/ }));
    fireEvent.click(screen.getByRole("button", { name: "View in 3D" }));

    expect(show).toHaveBeenCalledExactlyOnceWith(5291);
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
    expect(within(card).getByRole("button", { name: "View the molecule in 3D" })).toBeDefined();
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

  describe("with its trace", () => {
    function openTraced(trace: RetrievalTrace, answer = "Imatinib blocks BCR-ABL [1].") {
      const card = cardOf({
        id: "call_1",
        name: "search_labels",
        args: { drug: "Gleevec", section: "pharmacology" },
        result: IMATINIB_LABELS,
        trace,
      }) as Exclude<Card, { kind: "pending" }>;
      render(<ToolCard text="Step" card={card} answer={answer} current={false} />);
      fireEvent.click(screen.getByRole("button", { name: /^Step/ }));
      return screen.getByRole("button", { name: /^Step/ }).parentElement!;
    }

    function ranked(card: HTMLElement): HTMLElement[] {
      return within(within(card).getByRole("list", { name: "Passages by rank" })).getAllByRole(
        "listitem",
      );
    }

    function facts(card: HTMLElement): Record<string, string> {
      return Object.fromEntries(
        Array.from(card.querySelectorAll("dt")).map((term) => [
          term.textContent,
          term.nextElementSibling?.textContent ?? "",
        ]),
      );
    }

    it("shows each step of the search, the translation as skipped", () => {
      const card = openTraced(IMATINIB_TRACE);

      expect(facts(card)).toEqual({
        Translation: "Skipped searched with the question as written",
        Drugs: "Gleevec → imatinib · 1 labelNamed by the chat model when it called the search.",
        Sections: "Pharmacology moved to the top, the rest still searched",
        "Ranked by": "Embeddings: closest in meaning",
      });
    });

    it("shows the queries a translated search searched with", () => {
      const card = openTraced({
        ...IMATINIB_TRACE,
        translation: [
          { step: "rewrite 1", output: "imatinib mechanism of action" },
          { step: "rewrite 2", output: "How does Gleevec work?" },
        ],
      });

      expect(facts(card).Translation).toBe("imatinib mechanism of actionHow does Gleevec work?");
    });

    it("says why a translation failed and the question was searched as written", () => {
      const card = openTraced({ ...IMATINIB_TRACE, translation_error: "APITimeoutError" });

      expect(facts(card).Translation).toBe(
        "Skipped searched with the question as writtenThe translation gave no answer: APITimeoutError",
      );
    });

    it("ranks every candidate with its similarity and the section bonus, marking the cited one", () => {
      const card = openTraced(IMATINIB_TRACE);

      const rows = ranked(card);
      expect(rows.map((row) => row.querySelector("summary")?.textContent)).toEqual([
        "1Mechanism of action · Gleevec+0.15 section asked for0.71[1] cited",
        "2Pharmacokinetics · Gleevec+0.15 section asked for0.52[2]",
        "–How supplied · Gleevecdropped, below 0.300.21",
      ]);
      expect(rows.map((row) => row.querySelector("[data-cited]") !== null)).toEqual([
        true,
        false,
        false,
      ]);
      expect(rows[2].textContent).toContain("Gleevec tablets are supplied");
      expect(card.textContent).toContain("1 dropped for a similarity below 0.30.");
      expect(card.textContent).toContain("counts 0.15 higher in the ranking");
    });

    it("leaves out the bonus when the setup gives none", () => {
      const card = openTraced({ ...IMATINIB_TRACE, section_group_boost: 0 });

      expect(ranked(card).map((row) => row.querySelector("summary")?.textContent)).toEqual([
        "1Mechanism of action · Gleevec0.71[1] cited",
        "2Pharmacokinetics · Gleevec0.52[2]",
        "–How supplied · Gleevecdropped, below 0.300.21",
      ]);
      expect(card.textContent).not.toContain("higher in the ranking");
    });

    it("shows a filter the label filter read from the question, with a name outside the store", () => {
      const card = openTraced({
        ...IMATINIB_TRACE,
        filter_source: "model",
        filter: {
          ...IMATINIB_TRACE.filter!,
          unsupported: [{ ...TYLENOLL_NOT_SUPPORTED, status: "not_supported" } as never],
          section_groups: [],
        },
      });

      expect(facts(card).Drugs).toBe(
        "Gleevec → imatinib · 1 labelTylenoll not supportedRead from the question by the label filter.",
      );
      expect(facts(card).Sections).toBe("The whole label");
    });

    it("shows the ranks of both rankings in hybrid mode", () => {
      const card = openTraced({
        ...IMATINIB_TRACE,
        mode: "hybrid",
        candidates: IMATINIB_TRACE.candidates.map((candidate, index) => ({
          ...candidate,
          bm25_rank: index === 0 ? 4 : null,
        })),
      });

      expect(facts(card)["Ranked by"]).toBe("Keywords and embeddings, merged by rank");
      expect(ranked(card)[0].textContent).toContain("embeddings #1 · keywords #4");
      expect(card.textContent).not.toContain("section asked for");
    });

    it("says when a search scored nothing", () => {
      const card = openTraced({ ...IMATINIB_TRACE, filter: null, candidates: [] }, "");

      expect(facts(card).Drugs).toBe("AnyNo drug named, so every label was searched.");
      expect(card.textContent).toContain("No passage matched the question.");
      expect(within(card).queryByRole("list", { name: "Passages by rank" })).toBeNull();
    });
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

describe("in German", () => {
  beforeEach(() => localStorage.setItem(LANGUAGE_KEY, "de"));
  afterEach(() => localStorage.clear());

  it("writes the summary and the result in German", () => {
    const trigger = renderCard("resolve_drug", GLEEVEC_FOUND);
    expect(trigger.textContent).toBe("Step„Gleevec“ → imatinib");

    fireEvent.click(trigger);
    expect(trigger.parentElement!.textContent).toContain(
      "„Gleevec“ ist ein gespeicherter Name für imatinib (PubChem CID 5291).",
    );
  });

  it("names the properties in German", () => {
    const properties = openCard("get_properties", METFORMIN_PROPERTIES);

    expect(within(properties).getByRole("rowheader", { name: /^Molmasse/ })).toBeDefined();
    expect(properties.textContent).toContain("Atome außer Wasserstoff");
  });

  it("names the complex's facts in German", () => {
    const complex = openCard("get_complex", IMATINIB_COMPLEX);
    expect(within(complex).getByText("Zielprotein")).toBeDefined();
    expect(within(complex).getByText("Wasserstoffbrücken")).toBeDefined();
    expect(within(complex).getByRole("button", { name: "In 3D ansehen" })).toBeDefined();
  });

  it("says in German what a label search looked for, keeping the label's section names", () => {
    const card = openCard(
      "search_labels",
      IMATINIB_LABELS,
      { drug: "imatinib", section: "pharmacology" },
      "Imatinib blocks BCR-ABL [1].",
    );

    expect(card.textContent).toContain(
      `Gesucht nach „${IMATINIB_LABELS.question}“ in der Fachinformation von imatinib, den Abschnitten „Pharmacology“.`,
    );
    const first = within(card).getAllByRole("listitem")[0];
    expect(first.querySelector("summary")?.textContent).toBe(
      "[1] Gleevec · Mechanism of action · 13. Juli 2026zitiert",
    );
    expect(linkTo(first, /^Die Fachinformation auf DailyMed öffnen/)).toBe(
      IMATINIB_LABELS.passages[0].url,
    );
  });

  it("says in German that a name isn't supported", () => {
    const card = openCard("resolve_drug", TYLENOLL_NOT_SUPPORTED);

    expect(card.textContent).toContain("Nicht unterstützt");
    expect(card.textContent).toContain("„Tylenoll“ ist nicht in Moleculas Daten");
  });
});
