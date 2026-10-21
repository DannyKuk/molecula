import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, type Drug, resolveDrug } from "@/lib/api";
import { notSupported } from "@/lib/test-fixtures";

import { SupportedDrugs } from "./supported-drugs";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  resolveDrug: vi.fn(),
}));

const DRUGS: Drug[] = [
  { cid: 1983, name: "acetaminophen", aliases: ["Tylenol", "Paracetamol"], has_3d: false },
  { cid: 2519, name: "caffeine", aliases: [], has_3d: true },
  { cid: 5291, name: "imatinib", aliases: ["Gleevec", "Glivec"], has_3d: true },
];

beforeEach(() => {
  vi.mocked(resolveDrug).mockImplementation(async (name) => notSupported(name, []));
});

function renderList(onAsk = vi.fn()) {
  render(<SupportedDrugs drugs={DRUGS} onAsk={onAsk} />);
  return onAsk;
}

function search(query: string) {
  fireEvent.change(screen.getByRole("searchbox", { name: "Search by name or brand" }), {
    target: { value: query },
  });
}

function listedDrugs(): string[] {
  return screen
    .queryAllByRole("listitem")
    .flatMap((item) => within(item).queryAllByRole("button"))
    .map((button) => button.getAttribute("aria-labelledby"))
    .map((nameId) => document.getElementById(nameId ?? "")?.textContent ?? "");
}

describe("SupportedDrugs", () => {
  it("lists every drug from the data with its aliases and the count", () => {
    renderList();

    expect(listedDrugs()).toEqual(["acetaminophen", "caffeine", "imatinib"]);
    expect(
      screen.getByRole("button", { name: "acetaminophen", description: /^Tylenol, Paracetamol/ }),
    ).toBeDefined();
    expect(screen.getByRole("status").textContent).toBe(
      "3 supported drugs. Pick one to ask how it works.",
    );
  });

  it("marks only the drugs without a 3D structure", () => {
    renderList();

    expect(
      screen.getByRole("button", {
        name: "acetaminophen",
        description: "Tylenol, Paracetamol no 3D",
      }),
    ).toBeDefined();
    expect(
      screen.getByRole("button", { name: "imatinib", description: "Gleevec, Glivec" }),
    ).toBeDefined();
    const caffeine = screen.getByRole("button", { name: "caffeine" });
    expect(caffeine.getAttribute("aria-describedby")).toBeNull();
  });

  it("groups the drugs by letter and links each letter that has drugs", () => {
    renderList();

    expect(screen.getAllByRole("region").map((group) => group.getAttribute("aria-label"))).toEqual([
      "A",
      "C",
      "I",
    ]);
    const letters = within(screen.getByRole("navigation", { name: "Jump to a letter" }));
    expect(letters.getAllByRole("link").map((link) => link.textContent)).toEqual(["A", "C", "I"]);
    expect(letters.getByRole("link", { name: "I" }).getAttribute("href")).toBe("#drugs-I");
  });

  it("leaves the letters out while searching", () => {
    renderList();

    search("caf");

    expect(screen.queryByRole("navigation", { name: "Jump to a letter" })).toBeNull();
    expect(screen.getAllByRole("region").map((group) => group.getAttribute("aria-label"))).toEqual([
      "C",
    ]);
  });

  it.each([
    ["tylenol", "acetaminophen"],
    ["PARACETAMOL", "acetaminophen"],
    ["gleevec", "imatinib"],
    ["GLIVEC", "imatinib"],
    ["ImAtInIb", "imatinib"],
  ])("finds the drug by name or alias in any case: %s", (query, name) => {
    renderList();

    search(query);

    expect(listedDrugs()).toEqual([name]);
    expect(screen.getByRole("status").textContent).toBe(
      `1 of 3 supported drugs matches “${query}”.`,
    );
  });

  it("matches part of a name or brand and counts the matches", () => {
    renderList();

    search("le");

    expect(listedDrugs()).toEqual(["acetaminophen", "imatinib"]);
    expect(screen.getByRole("status").textContent).toBe("2 of 3 supported drugs match “le”.");
  });

  it("says the name is not supported and gives the count when nothing matches", async () => {
    renderList();

    search("  aspirin ");

    await waitFor(() => expect(resolveDrug).toHaveBeenCalledWith("aspirin", expect.anything()));
    expect(listedDrugs()).toEqual([]);
    expect(screen.getByRole("status").textContent).toBe(
      "“aspirin” is not supported. Molecula answers only about its 3 supported drugs.",
    );
    expect(screen.queryByText(/Did you mean/)).toBeNull();
  });

  it("offers the closest supported names when nothing matches", async () => {
    vi.mocked(resolveDrug).mockResolvedValue(
      notSupported("Gleevek", [
        { alias: "Gleevec", cid: 5291, name: "imatinib" },
        { alias: "Glivec", cid: 5291, name: "imatinib" },
      ]),
    );
    renderList();

    search("Gleevek");

    expect(await screen.findByRole("button", { name: "Gleevec (imatinib)" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Glivec (imatinib)" })).toBeDefined();
    expect(screen.getByText(/Did you mean/).textContent).toBe(
      "Did you mean Gleevec (imatinib) or Glivec (imatinib)?",
    );
    expect(screen.getByRole("status").textContent).toBe(
      "“Gleevek” is not supported. Molecula answers only about its 3 supported drugs.",
    );
    expect(listedDrugs()).toEqual([]);
  });

  it("selects the suggested drug when a suggestion is clicked, without asking about it", async () => {
    vi.mocked(resolveDrug).mockResolvedValue(
      notSupported("Gleevek", [{ alias: "Gleevec", cid: 5291, name: "imatinib" }]),
    );
    const onAsk = renderList();

    search("Gleevek");
    fireEvent.click(await screen.findByRole("button", { name: "Gleevec (imatinib)" }));

    expect(screen.getByRole<HTMLInputElement>("searchbox").value).toBe("imatinib");
    expect(listedDrugs()).toEqual(["imatinib"]);
    expect(screen.queryByText(/Did you mean/)).toBeNull();
    expect(onAsk).not.toHaveBeenCalled();
  });

  it("names a suggested generic name once", async () => {
    vi.mocked(resolveDrug).mockResolvedValue(
      notSupported("imatinb", [{ alias: "imatinib", cid: 5291, name: "imatinib" }]),
    );
    renderList();

    search("imatinb");

    expect((await screen.findByText(/Did you mean/)).textContent).toBe("Did you mean imatinib?");
  });

  it("says a salt name is supported under another name and offers that drug", async () => {
    vi.mocked(resolveDrug).mockResolvedValue({
      query: "imatinib mesylate",
      status: "found",
      compound: {
        cid: 5291,
        name: "imatinib",
        inchikey: "KTUFNOKKBVMGRW-UHFFFAOYSA-N",
        smiles: "CC1=C(C=C(C=C1)NC(=O)C2=CC=C(C=C2)CN3CCN(CC3)C)NC4=NC=CC(=N4)C5=CN=CC=C5",
        formula: "C29H31N7O",
        molecular_weight: 493.6,
        xlogp: 3.5,
        tpsa: 86.3,
        hbond_donors: 2,
        hbond_acceptors: 7,
        rotatable_bonds: 7,
        heavy_atoms: 37,
        has_3d: true,
        conformer_source: "pubchem",
        source: "PubChem",
        source_url: "https://pubchem.ncbi.nlm.nih.gov/compound/5291",
      },
      matched_alias: "imatinib",
      match_kind: "name",
      suggestions: [],
    });
    renderList();

    search("imatinib mesylate");
    const suggestion = await screen.findByRole("button", { name: "imatinib" });

    expect(screen.getByRole("status").textContent).toBe(
      "“imatinib mesylate” is supported under another name.",
    );
    fireEvent.click(suggestion);
    expect(listedDrugs()).toEqual(["imatinib"]);
  });

  it("falls back to the not supported message when the lookup fails", async () => {
    vi.mocked(resolveDrug).mockRejectedValue(new ApiError("/drugs/resolve?name=Gleevek", 503));
    renderList();

    search("Gleevek");

    await waitFor(() => expect(resolveDrug).toHaveBeenCalled());
    await new Promise((resolve) => setTimeout(resolve, 0));
    expect(screen.getByRole("status").textContent).toBe(
      "“Gleevek” is not supported. Molecula answers only about its 3 supported drugs.",
    );
    expect(screen.queryByText(/Did you mean/)).toBeNull();
  });

  it("looks the name up once typing pauses, not on every keystroke", async () => {
    renderList();

    search("as");
    search("asp");
    search("aspirin");

    await waitFor(() =>
      expect(resolveDrug).toHaveBeenCalledExactlyOnceWith("aspirin", expect.any(AbortSignal)),
    );
  });

  it("does not look the name up while the list has matches", async () => {
    renderList();

    search("tylenol");

    await new Promise((resolve) => setTimeout(resolve, 400));
    expect(resolveDrug).not.toHaveBeenCalled();
  });

  it("shows every drug again when the search is cleared", () => {
    renderList();

    search("aspirin");
    search("");

    expect(listedDrugs()).toEqual(["acetaminophen", "caffeine", "imatinib"]);
  });

  it("asks how the drug works when a drug is clicked", () => {
    const onAsk = renderList();

    fireEvent.click(screen.getByRole("button", { name: "imatinib" }));

    expect(onAsk).toHaveBeenCalledExactlyOnceWith("How does imatinib work?");
  });
});
