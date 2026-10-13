import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Source } from "@/lib/chat";
import { IMATINIB_SOURCES, OPENFDA_DISCLAIMER } from "@/lib/test-fixtures";

import { AnswerSources } from "./answer-sources";

const PDE5A: Source = {
  kind: "chembl",
  name: "cGMP-specific 3',5'-cyclic phosphodiesterase",
  url: "https://www.ebi.ac.uk/chembl/explore/target/CHEMBL1827",
  section: null,
  effective_time: null,
  ref: null,
};

function links(): [string, string | null][] {
  return screen
    .queryAllByRole("link")
    .map((link) => [link.textContent ?? "", link.getAttribute("href")]);
}

describe("AnswerSources", () => {
  it("lists the pages the tools used and the disclaimer under an answer that cites its labels", () => {
    render(
      <AnswerSources
        answer="Imatinib blocks BCR-ABL [1]."
        sources={IMATINIB_SOURCES}
        disclaimer={OPENFDA_DISCLAIMER}
      />,
    );

    expect(screen.queryByText("Based on")).toBeNull();
    expect(screen.getByText("Also from")).toBeDefined();
    expect(links()).toEqual([
      ["PubChem · imatinib", "https://pubchem.ncbi.nlm.nih.gov/compound/5291"],
    ]);
    expect(screen.getByText(OPENFDA_DISCLAIMER)).toBeDefined();
  });

  it("names each label read once when the answer cites none of its passages", () => {
    render(
      <AnswerSources
        answer="Ibuprofen and naproxen both block COX enzymes."
        sources={IMATINIB_SOURCES}
        disclaimer={OPENFDA_DISCLAIMER}
      />,
    );

    expect(screen.getByText("Based on")).toBeDefined();
    expect(links()[0]).toEqual(["Gleevec label", IMATINIB_SOURCES[0].url]);
    expect(links()).toHaveLength(2);
  });

  it("counts a citation in gpt-oss's own brackets as citing the label", () => {
    render(
      <AnswerSources
        answer="Imatinib blocks BCR-ABL【2】."
        sources={IMATINIB_SOURCES}
        disclaimer={null}
      />,
    );

    expect(screen.queryByText("Based on")).toBeNull();
  });

  it("lists a ChEMBL target without a disclaimer when no label text was used", () => {
    render(
      <AnswerSources answer="Sildenafil binds PDE5A【1】." sources={[PDE5A]} disclaimer={null} />,
    );

    expect(links()).toEqual([["ChEMBL · cGMP-specific 3',5'-cyclic phosphodiesterase", PDE5A.url]]);
    expect(screen.getByRole("link").getAttribute("target")).toBe("_blank");
    expect(screen.getByRole("link").getAttribute("rel")).toBe("noopener noreferrer");
    expect(screen.getByText("From")).toBeDefined();
    expect(screen.queryByText(/openFDA/)).toBeNull();
  });

  it("shows nothing for an answer without sources", () => {
    const { container } = render(
      <AnswerSources
        answer="Molecula only answers questions about medicines."
        sources={[]}
        disclaimer={null}
      />,
    );

    expect(container.innerHTML).toBe("");
  });
});
