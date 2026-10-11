import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Drug } from "@/lib/api";

import { SupportedDrugs } from "./supported-drugs";

const DRUGS: Drug[] = [
  { cid: 1983, name: "acetaminophen", aliases: ["Tylenol", "Paracetamol"], has_3d: false },
  { cid: 2519, name: "caffeine", aliases: [], has_3d: true },
  { cid: 5291, name: "imatinib", aliases: ["Gleevec", "Glivec"], has_3d: true },
];

afterEach(cleanup);

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
  return within(screen.getByRole("list"))
    .queryAllByRole("button")
    .map((button) => button.getAttribute("aria-labelledby"))
    .map((nameId) => document.getElementById(nameId ?? "")?.textContent ?? "");
}

describe("SupportedDrugs", () => {
  it("lists every drug from the data with its aliases and the count", () => {
    renderList();

    expect(listedDrugs()).toEqual(["acetaminophen", "caffeine", "imatinib"]);
    expect(
      screen.getByRole("button", { name: "acetaminophen", description: "Tylenol, Paracetamol" }),
    ).toBeDefined();
    expect(screen.getByRole("status").textContent).toBe(
      "3 supported drugs. Pick one to ask how it works.",
    );
  });

  it("shows the 3D structure badge only on drugs that have one", () => {
    renderList();

    expect(
      screen.getByRole("button", { name: "imatinib", description: "Gleevec, Glivec 3D structure" }),
    ).toBeDefined();
    expect(
      screen.getByRole("button", { name: "caffeine", description: "3D structure" }),
    ).toBeDefined();
    const acetaminophen = screen.getByRole("button", { name: "acetaminophen" });
    expect(within(acetaminophen).queryByText("3D structure")).toBeNull();
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

  it("says the name is not supported and gives the count when nothing matches", () => {
    renderList();

    search("  aspirin ");

    expect(listedDrugs()).toEqual([]);
    expect(screen.getByRole("status").textContent).toBe(
      "“aspirin” is not supported. Molecula answers only about its 3 supported drugs.",
    );
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
