import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { Source } from "@/lib/chat";
import { IMATINIB_SOURCES } from "@/lib/test-fixtures";

import { PrintedSources } from "./answer-sources";

const PDE5A: Source = {
  kind: "chembl",
  name: "cGMP-specific 3',5'-cyclic phosphodiesterase",
  url: "https://www.ebi.ac.uk/chembl/explore/target/CHEMBL1827",
  section: null,
  effective_time: null,
  ref: 1,
};

function credit(): HTMLElement | null {
  return screen.queryByText(/^Data provided by the U\.S\. Food and Drug Administration/);
}

describe("PrintedSources", () => {
  it("prints every source with its number, and credits openFDA for label text", () => {
    render(<PrintedSources sources={IMATINIB_SOURCES} />);

    expect(screen.getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      `[1] Gleevec – Mechanism of action – ${IMATINIB_SOURCES[0].url}`,
      `[2, 3] Gleevec – Pharmacokinetics – ${IMATINIB_SOURCES[0].url}`,
      "[4] PubChem – imatinib – https://pubchem.ncbi.nlm.nih.gov/compound/5291",
    ]);
    expect(credit()).not.toBeNull();
  });

  it("gives no openFDA credit without label text", () => {
    render(<PrintedSources sources={[PDE5A]} />);

    expect(credit()).toBeNull();
  });

  it("prints nothing for an answer without sources", () => {
    const { container } = render(<PrintedSources sources={[]} />);

    expect(container.innerHTML).toBe("");
  });
});
