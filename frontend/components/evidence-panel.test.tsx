import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { Source } from "@/lib/chat";
import { startTurn, type Turn } from "@/lib/chat-turn";
import type { Shown } from "@/lib/evidence";
import { IMATINIB_SOURCES } from "@/lib/test-fixtures";
import { ACETAMINOPHEN_NO_COMPLEX, IMATINIB_COMPLEX } from "@/lib/test-tool-results";
import type { StructureTarget } from "@/lib/tool-cards";

import { EvidencePanel } from "./evidence-panel";

// jsdom has no WebGL; the 3D view only needs to be on the page.
vi.mock("./structure/structure-panel", () => ({
  StructurePanel: ({ target }: { target: StructureTarget }) => <p>3D view of {target.name}</p>,
}));

const MECHANISM = "Imatinib mesylate is a protein-tyrosine kinase inhibitor that inhibits BCR-ABL.";
const CHEMBL_ONLY: Source = {
  kind: "chembl",
  name: "cGMP-specific 3',5'-cyclic phosphodiesterase",
  url: "https://www.ebi.ac.uk/chembl/explore/target/CHEMBL1827",
  section: null,
  effective_time: null,
  ref: 1,
};

function complexStep(drug: string, result: unknown) {
  return {
    text: `Getting the complex of ${drug}`,
    tool: { id: `call_${drug}`, name: "get_complex", args: { drug }, result },
  };
}

function answered(question: string, changes: Partial<Turn> = {}): Turn {
  return { ...startTurn(question), state: "done", answer: "An answer.", ...changes };
}

const IMATINIB_TURN = answered("How does imatinib work?", {
  answer: "Imatinib blocks BCR-ABL [1].",
  steps: [complexStep("imatinib", IMATINIB_COMPLEX)],
  sources: IMATINIB_SOURCES,
  passages: { 1: { ref: 1, text: MECHANISM } },
});

function renderPanel(turns: Turn[], shown: Shown & { turn: number }) {
  const onShow = vi.fn();
  render(<EvidencePanel turns={turns} shown={shown} onShow={onShow} />);
  return onShow;
}

function sourceCards(): HTMLElement[] {
  return within(screen.getByRole("list", { name: "Sources of this answer" })).getAllByRole(
    "listitem",
  );
}

describe("EvidencePanel", () => {
  it("names the answer it shows and steps to its neighbours on their own tabs", () => {
    const turns = [IMATINIB_TURN, answered("What is metformin for?")];
    const onShow = renderPanel(turns, { turn: 1, tab: "sources" });

    expect(screen.getByRole("heading", { level: 2 }).textContent).toBe("Answer 2 of 2");
    expect(screen.getByText("What is metformin for?")).toBeDefined();
    expect(screen.getByRole("button", { name: "Next answer" }).hasAttribute("disabled")).toBe(true);

    fireEvent.click(screen.getByRole("button", { name: "Previous answer" }));

    expect(onShow).toHaveBeenCalledExactlyOnceWith({ turn: 0, tab: "3d" });
  });

  it("lists the sources as numbered cards with the passage, its label's date and its link", () => {
    renderPanel([IMATINIB_TURN], { turn: 0, tab: "sources" });

    const [mechanism, , , pubchem] = sourceCards();
    expect(sourceCards()).toHaveLength(4);
    expect(within(mechanism).getByText("[1]")).toBeDefined();
    expect(mechanism.textContent).toContain("Gleevec · Mechanism of action");
    expect(mechanism.textContent).toContain("Cited");
    expect(mechanism.textContent).toContain("FDA label of Jul 13, 2026");
    expect(mechanism.textContent).toContain(MECHANISM);
    const label = within(mechanism).getByRole("link", { name: "Open the label on DailyMed" });
    expect(label.getAttribute("href")).toBe(IMATINIB_SOURCES[0].url);
    expect(label.getAttribute("target")).toBe("_blank");
    expect(pubchem.textContent).toContain("PubChem · imatinib");
    expect(pubchem.textContent).not.toContain("Cited");
    expect(within(pubchem).getByRole("link", { name: "Open on PubChem" })).toBeDefined();
    expect(screen.getByRole("link", { name: "openFDA" }).getAttribute("rel")).toBe(
      "noopener noreferrer",
    );
  });

  it("gives no openFDA credit when no label text was used", () => {
    renderPanel([answered("What does sildenafil bind?", { sources: [CHEMBL_ONLY] })], {
      turn: 0,
      tab: "sources",
    });

    expect(sourceCards()).toHaveLength(1);
    expect(screen.queryByRole("link", { name: "openFDA" })).toBeNull();
  });

  it("highlights the sources a citation chip opened", () => {
    renderPanel([IMATINIB_TURN], { turn: 0, tab: "sources", refs: [2, 3] });

    const highlighted = sourceCards().map((card) => card.hasAttribute("data-highlighted"));
    expect(highlighted).toEqual([false, true, true, false]);
  });

  it("says the sources come once the answer is written", () => {
    renderPanel([startTurn("How does imatinib work?")], { turn: 0, tab: "sources" });

    expect(screen.getByText("The sources show here once the answer is written.")).toBeDefined();
  });

  it("shows the answer's structure and every structure of the chat", () => {
    const turns = [IMATINIB_TURN, answered("What is metformin for?")];
    const onShow = renderPanel(turns, { turn: 1, tab: "3d" });

    expect(screen.getByText("This answer didn't look up a structure.")).toBeDefined();
    const inChat = screen.getByRole("region", { name: "Structures in this chat" });
    fireEvent.click(within(inChat).getByRole("button", { name: /^imatinib.*answer 1$/ }));

    expect(onShow).toHaveBeenCalledExactlyOnceWith({ turn: 0, tab: "3d", cid: 5291 });
  });

  it("switches between the drugs of an answer that looked up several structures", () => {
    const turn = answered("Show imatinib and acetaminophen in 3D", {
      steps: [
        complexStep("imatinib", IMATINIB_COMPLEX),
        complexStep("acetaminophen", ACETAMINOPHEN_NO_COMPLEX),
      ],
    });
    const onShow = renderPanel([turn], { turn: 0, tab: "3d", cid: 1983 });

    expect(screen.getByText("3D view of acetaminophen")).toBeDefined();
    const drugs = screen.getByRole("group", { name: "Drug in 3D" });
    fireEvent.click(within(drugs).getByRole("button", { name: "imatinib" }));

    expect(onShow).toHaveBeenCalledExactlyOnceWith({ turn: 0, tab: "3d", cid: 5291 });
  });

  it("lists the steps and opens a structure from them in the 3D tab", () => {
    const onShow = renderPanel([IMATINIB_TURN], { turn: 0, tab: "steps" });

    fireEvent.click(screen.getByRole("button", { name: /^Getting the complex of imatinib/ }));
    fireEvent.click(screen.getByRole("button", { name: "View in 3D" }));

    expect(onShow).toHaveBeenCalledExactlyOnceWith({ turn: 0, tab: "3d", cid: 5291 });
  });
});
