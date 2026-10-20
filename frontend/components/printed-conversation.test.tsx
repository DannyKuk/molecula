import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Complex } from "@/lib/api";
import type { Source } from "@/lib/chat";
import { startTurn, type Turn } from "@/lib/chat-turn";
import type { Picture } from "@/lib/printed-pictures";
import { METAL_COMPLEX, SMALL_COMPLEX } from "@/lib/test-complexes";
import { IMATINIB_SOURCES } from "@/lib/test-fixtures";
import { IMATINIB_COMPLEX } from "@/lib/test-tool-results";
import type { DrugComplex, StructureTarget } from "@/lib/tool-cards";

import {
  askedTime,
  PrintedEnd,
  PrintedHeader,
  PrintedSources,
  PrintedStructure,
} from "./printed-conversation";
import { COLORS } from "./structure/scene";

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

describe("PrintedStructure", () => {
  const imatinib: StructureTarget = {
    cid: 5291,
    name: "imatinib",
    complex: IMATINIB_COMPLEX as DrugComplex,
  };
  const acetaminophen: StructureTarget = { cid: 1983, name: "acetaminophen", complex: null };
  const PNG = "data:image/png;base64,iVBORw0KGgo=";

  function legend(): string[] {
    const colours = screen.getByRole("list", { name: "Colours" });
    return within(colours)
      .getAllByRole("listitem")
      .map((item) => item.textContent);
  }

  it("prints the picture with the drug, its target and PDB ID, on paper only", () => {
    render(
      <PrintedStructure
        target={imatinib}
        picture={{ status: "ready", png: PNG, complex: SMALL_COMPLEX, elements: ["N", "O"] }}
      />,
    );

    const figure = screen.getByRole("figure", { name: "3D structure of imatinib" });
    expect(figure.className).toContain("hidden");
    expect(figure.className).toContain("print:block");
    const image = within(figure).getByRole("img", { name: /^Imatinib in ABL1 \(BCR-ABL\),/ });
    expect(image.getAttribute("src")).toBe(PNG);
    expect(within(figure).getByText("PDB 2HYY · Homo sapiens · 6 hydrogen bonds")).toBeDefined();
  });

  it("draws the legend of the binding site, with metal bonds and cofactors when it has them", () => {
    const drawn = (complex: Complex): Picture => ({
      status: "ready",
      png: PNG,
      complex,
      elements: ["Cl", "N", "O"],
    });
    const { rerender } = render(
      <PrintedStructure target={imatinib} picture={drawn(SMALL_COMPLEX)} />,
    );
    expect(legend()).toEqual([
      "imatinib carbons",
      "chlorine",
      "nitrogen",
      "oxygen",
      "hydrogen bond",
      "residues within 4 Å",
    ]);

    rerender(<PrintedStructure target={imatinib} picture={drawn(METAL_COMPLEX)} />);
    expect(legend()).toEqual([
      "imatinib carbons",
      "chlorine",
      "nitrogen",
      "oxygen",
      "hydrogen bond",
      "metal bond",
      "cofactor",
      "residues within 4 Å",
    ]);
    // Drawn, because browsers leave background colours out of print.
    expect(screen.getByRole("list", { name: "Colours" }).querySelectorAll("svg")).toHaveLength(8);
    const fills = [...screen.getByRole("list", { name: "Colours" }).querySelectorAll("circle")].map(
      (circle) => circle.getAttribute("fill"),
    );
    expect(fills).toEqual([
      COLORS.paper.drug,
      COLORS.paper.elements.Cl,
      COLORS.paper.elements.N,
      COLORS.paper.elements.O,
    ]);
  });

  it("prints a drug without a complex as the molecule alone, with the legend of its colours", () => {
    render(
      <PrintedStructure
        target={acetaminophen}
        picture={{ status: "ready", png: PNG, complex: null, elements: ["H", "N", "O"] }}
      />,
    );

    expect(screen.getByRole("img", { name: /^Acetaminophen,/ })).toBeDefined();
    expect(screen.getByText(/the molecule alone/)).toBeDefined();
    expect(legend()).toEqual(["acetaminophen carbons", "hydrogen", "nitrogen", "oxygen"]);
  });

  it("prints a line instead of a picture that couldn't be drawn, or a drug without a 3D model", () => {
    const { rerender } = render(
      <PrintedStructure target={imatinib} picture={{ status: "failed" }} />,
    );
    expect(screen.getByText("The 3D picture of imatinib couldn't be drawn.")).toBeDefined();
    expect(screen.queryByRole("img")).toBeNull();

    rerender(<PrintedStructure target={acetaminophen} picture={{ status: "missing" }} />);
    expect(screen.getByText(/^No 3D model: .* acetaminophen is too large\.$/)).toBeDefined();
  });

  it("points to the export menu when the print didn't start there", () => {
    render(<PrintedStructure target={imatinib} picture={undefined} />);

    expect(
      screen.getByText(/^For the 3D picture of imatinib, print from the chat's export menu/),
    ).toBeDefined();
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
