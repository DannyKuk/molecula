import { readFileSync } from "node:fs";
import path from "node:path";

import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useImperativeHandle } from "react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { API_URL } from "@/lib/api";
import { LANGUAGE_KEY } from "@/lib/language";
import IMATINIB_2HYY from "@/lib/fixtures/complex-5291.json";
import { METAL_COMPLEX, SMALL_COMPLEX } from "@/lib/test-complexes";
import { IMATINIB_COMPLEX, METFORMIN_COMPLEX } from "@/lib/test-tool-results";
import type { DrugComplex } from "@/lib/tool-cards";

import { COLORS } from "./scene";
import { StructurePanel } from "./structure-panel";
import type { StructureViewerHandle } from "./structure-viewer";

const replay = vi.fn();

// jsdom has no WebGL; the stub shows what the viewer was asked to draw.
vi.mock("./structure-viewer", () => ({
  StructureViewer: ({
    data,
    mode,
    label,
    onError,
    ref,
  }: {
    data: { kind: string };
    mode: string;
    label: string;
    onError: () => void;
    ref?: React.Ref<StructureViewerHandle>;
  }) => {
    useImperativeHandle(ref, () => ({ replay, reset: vi.fn() }));
    return (
      <div role="img" aria-label={label} data-kind={data.kind} data-mode={mode}>
        <button type="button" onClick={onError}>
          Lose WebGL
        </button>
      </div>
    );
  },
}));

let reducedMotion = false;

// Defined for the whole file, not per test: effects still running after a test ends read it.
beforeAll(() => {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: (query: string) => ({
      matches: query === "(prefers-reduced-motion: reduce)" && reducedMotion,
      addEventListener: () => {},
      removeEventListener: () => {},
    }),
  });
});

beforeEach(() => {
  reducedMotion = false;
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function stubFetch(...responses: (Response | Error)[]) {
  const fetchMock = vi.fn();
  for (const response of responses) {
    if (response instanceof Error) fetchMock.mockRejectedValueOnce(response);
    else fetchMock.mockResolvedValueOnce(response);
  }
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

const imatinib = { cid: 5291, name: "imatinib", complex: IMATINIB_COMPLEX as DrugComplex };
const acetaminophen = { cid: 1983, name: "acetaminophen", complex: null };
const ACETAMINOPHEN_SDF = readFileSync(
  path.join(__dirname, "../../lib/fixtures/structure-1983.sdf"),
  "utf8",
);

describe("StructurePanel", () => {
  it("shows a drug with a complex in its binding site, and switches what the view shows", async () => {
    const fetchMock = stubFetch(Response.json(SMALL_COMPLEX));
    render(<StructurePanel target={imatinib} />);

    const view = await screen.findByRole("img", { name: "Imatinib in ABL1 (BCR-ABL), in 3D" });
    expect(fetchMock.mock.calls[0][0]).toBe(`${API_URL}/drugs/5291/complex`);
    expect(screen.getByText("PDB 2HYY · Homo sapiens · 6 hydrogen bonds")).toBeDefined();
    expect(view.dataset).toMatchObject({ kind: "complex", mode: "site" });
    expect(pressed()).toBe("Binding site");
    expect(screen.getByText("hydrogen bond")).toBeDefined();
    expect(screen.queryByText("metal bond")).toBeNull();
    expect(screen.queryByText("cofactor")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Whole protein" }));
    expect(view.dataset.mode).toBe("protein");
    expect(screen.getByText("protein backbone")).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "Molecule" }));
    expect(view.dataset.mode).toBe("molecule");
    expect(screen.queryByText("hydrogen bond")).toBeNull();
    expect(screen.queryByRole("button", { name: "Replay binding" })).toBeNull();
  });

  it("puts the counts on the screen, and draws the legend in the view's colours", async () => {
    stubFetch(Response.json(METAL_COMPLEX));
    render(<StructurePanel target={imatinib} />);

    expect(await screen.findByText("3 atoms")).toBeDefined();
    expect(screen.getByText("2 residues")).toBeDefined();
    expect(screen.getByText("3 H-bonds")).toBeDefined();
    expect(swatch("imatinib carbons").backgroundColor).toBe(css(COLORS.screen.drug));
    expect(swatch("nitrogen").backgroundColor).toBe(css(COLORS.screen.elements.N));
    expect(swatch("oxygen").backgroundColor).toBe(css(COLORS.screen.elements.O));
    expect(swatch("hydrogen bond").borderColor).toBe(css(COLORS.screen.hbond));
    expect(swatch("metal bond").borderColor).toBe(css(COLORS.screen.coordination));
    expect(swatch("cofactor").borderColor).toBe(css(COLORS.screen.cofactor));
    expect(swatch("residues within 4 Å").borderColor).toBe(css(COLORS.screen.pocket));

    fireEvent.click(screen.getByRole("button", { name: "Whole protein" }));
    expect(swatch("protein backbone").borderColor).toBe(css(COLORS.screen.trace));
  });

  it("names the drug's carbons and the nitrogen, oxygen and sulfur the view draws, in every view", async () => {
    stubFetch(Response.json(IMATINIB_2HYY));
    render(<StructurePanel target={imatinib} />);

    expect(await screen.findByText("imatinib carbons")).toBeDefined();
    // The sulfur is the pocket methionines', so it leaves the legend with the pocket.
    expect(swatch("sulfur").backgroundColor).toBe(css(COLORS.screen.elements.S));

    fireEvent.click(screen.getByRole("button", { name: "Molecule" }));
    expect(screen.getByText("imatinib carbons")).toBeDefined();
    expect(screen.getByText("nitrogen")).toBeDefined();
    expect(screen.getByText("oxygen")).toBeDefined();
    expect(screen.queryByText("sulfur")).toBeNull();
  });

  it("names a drug's chlorine in its own colour, in every view", async () => {
    const chlorine = { name: "CL1", element: "Cl", xyz: [13, 0, 0] };
    stubFetch(
      Response.json({
        ...SMALL_COMPLEX,
        ligand: { ...SMALL_COMPLEX.ligand, atoms: [...SMALL_COMPLEX.ligand.atoms, chlorine] },
      }),
    );
    render(<StructurePanel target={imatinib} />);

    expect(await screen.findByText("chlorine")).toBeDefined();
    expect(swatch("chlorine").backgroundColor).toBe(css(COLORS.screen.elements.Cl));

    fireEvent.click(screen.getByRole("button", { name: "Molecule" }));
    expect(screen.getByText("chlorine")).toBeDefined();
  });

  it("explains the metal bonds and cofactors of a complex that has them", async () => {
    stubFetch(Response.json(METAL_COMPLEX));
    render(<StructurePanel target={imatinib} />);

    expect(await screen.findByText("metal bond")).toBeDefined();
    expect(screen.getByText("cofactor")).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "Molecule" }));
    expect(screen.queryByText("metal bond")).toBeNull();
    expect(screen.queryByText("cofactor")).toBeNull();
  });

  it("replays the binding", async () => {
    stubFetch(Response.json(SMALL_COMPLEX));
    render(<StructurePanel target={imatinib} />);

    fireEvent.click(await screen.findByRole("button", { name: "Replay binding" }));

    expect(replay).toHaveBeenCalledOnce();
  });

  it("shows a drug without a complex as the molecule alone, without the switch", async () => {
    const fetchMock = stubFetch(new Response(ACETAMINOPHEN_SDF));
    render(<StructurePanel target={acetaminophen} />);

    const view = await screen.findByRole("img", { name: "Acetaminophen, in 3D" });
    expect(fetchMock.mock.calls[0][0]).toBe(`${API_URL}/drugs/1983/structure`);
    expect(view.dataset).toMatchObject({ kind: "molecule", mode: "molecule" });
    expect(screen.queryByRole("group", { name: "What the 3D view shows" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Replay binding" })).toBeNull();
    expect(screen.getByText("11 atoms")).toBeDefined();
    expect(screen.queryByText(/residue/)).toBeNull();
    expect(swatch("acetaminophen carbons").backgroundColor).toBe(css(COLORS.screen.drug));
    expect(swatch("hydrogen").backgroundColor).toBe(css(COLORS.screen.elements.H));
    expect(screen.getByText("nitrogen")).toBeDefined();
    expect(screen.getByText("oxygen")).toBeDefined();
  });

  it("says why a drug without a 3D structure has no view", async () => {
    stubFetch(Response.json({ detail: "insulin glargine has no 3D structure." }, { status: 404 }));
    render(<StructurePanel target={{ cid: 118984454, name: "insulin glargine", complex: null }} />);

    expect(
      await screen.findByText(
        "No 3D model: Molecula has them for small-molecule drugs only, and insulin glargine is too large.",
      ),
    ).toBeDefined();
    expect(screen.queryByText(/the molecule alone/)).toBeNull();
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.queryByRole("button", { name: "Full screen" })).toBeNull();
  });

  it("offers to try again when the structure couldn't be loaded", async () => {
    const fetchMock = stubFetch(new TypeError("Failed to fetch"), new Response("1983\n$$$$\n"));
    render(<StructurePanel target={acetaminophen} />);

    const alert = await screen.findByRole("alert");
    fireEvent.click(within(alert).getByRole("button", { name: "Try again" }));

    expect(await screen.findByRole("img", { name: "Acetaminophen, in 3D" })).toBeDefined();
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("treats a missing complex as a failure, not as a drug without 3D", async () => {
    stubFetch(Response.json({ detail: "imatinib has no reviewed complex." }, { status: 404 }));
    render(<StructurePanel target={imatinib} />);

    expect(await screen.findByRole("alert")).toBeDefined();
    expect(screen.queryByText(/No 3D model/)).toBeNull();
  });

  it("says the structure couldn't be loaded when the view can't be drawn", async () => {
    stubFetch(Response.json(SMALL_COMPLEX));
    render(<StructurePanel target={imatinib} />);

    fireEvent.click(await screen.findByRole("button", { name: "Lose WebGL" }));

    expect(screen.getByRole("alert").textContent).toContain("couldn't be loaded");
    expect(screen.queryByRole("img")).toBeNull();
  });

  it("offers no binding replay when the system asks for reduced motion", async () => {
    reducedMotion = true;
    stubFetch(Response.json(SMALL_COMPLEX));
    render(<StructurePanel target={imatinib} />);

    expect(await screen.findByRole("button", { name: "Reset view" })).toBeDefined();
    expect(screen.queryByRole("button", { name: "Replay binding" })).toBeNull();
  });

  it("puts a stand-in structure's caption above the view", async () => {
    stubFetch(Response.json(SMALL_COMPLEX));
    render(
      <StructurePanel
        target={{ cid: 4091, name: "metformin", complex: METFORMIN_COMPLEX as DrugComplex }}
      />,
    );

    expect(await screen.findByRole("img")).toBeDefined();
    expect(screen.getByText(METFORMIN_COMPLEX.caption)).toBeDefined();
    expect(screen.getByText("PDB 8ZSQ · Sus scrofa · 0 hydrogen bonds")).toBeDefined();
  });

  it("opens the same view full screen, keeping the chosen view", async () => {
    stubFetch(Response.json(SMALL_COMPLEX));
    render(<StructurePanel target={imatinib} />);
    fireEvent.click(await screen.findByRole("button", { name: "Whole protein" }));

    fireEvent.click(screen.getByRole("button", { name: "Full screen" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByRole("img").dataset.mode).toBe("protein");
    expect(within(dialog).getByRole("button", { name: "Replay binding" })).toBeDefined();
    await waitFor(() => expect(screen.getAllByRole("img", { hidden: true })).toHaveLength(2));
  });
});

describe("StructurePanel in German", () => {
  afterEach(() => localStorage.clear());

  it("names the view, its switch, its counts and its legend in German", async () => {
    localStorage.setItem(LANGUAGE_KEY, "de");
    stubFetch(Response.json(METAL_COMPLEX));
    render(<StructurePanel target={imatinib} />);

    expect(await screen.findByText("3 Atome")).toBeDefined();
    expect(screen.getByRole("img", { name: "Imatinib an ABL1 (BCR-ABL), in 3D" })).toBeDefined();
    expect(screen.getByText("PDB 2HYY · Homo sapiens · 6 Wasserstoffbrücken")).toBeDefined();
    const modes = screen.getByRole("group", { name: "Was die 3D-Ansicht zeigt" });
    expect(
      within(modes)
        .getAllByRole("button")
        .map((button) => button.textContent),
    ).toEqual(["Molekül", "Bindungsstelle", "Ganzes Protein"]);
    expect(swatch("Kohlenstoffatome von imatinib").backgroundColor).toBe(css(COLORS.screen.drug));
    expect(swatch("Stickstoff").backgroundColor).toBe(css(COLORS.screen.elements.N));
    expect(swatch("Metallbindung").borderColor).toBe(css(COLORS.screen.coordination));
    expect(screen.getByRole("button", { name: "Ansicht zurücksetzen" })).toBeDefined();
    expect(screen.getByText("Ziehen zum Drehen · Scrollen zum Zoomen")).toBeDefined();
  });

  it("says in German when the structure couldn't be loaded", async () => {
    localStorage.setItem(LANGUAGE_KEY, "de");
    stubFetch(new Error("offline"));
    render(<StructurePanel target={imatinib} />);

    expect((await screen.findByRole("alert")).textContent).toContain(
      "Die 3D-Struktur konnte nicht geladen werden.",
    );
    expect(screen.getByRole("button", { name: "Noch einmal versuchen" })).toBeDefined();
  });
});

function pressed(): string | null {
  const group = screen.getByRole("group", { name: "What the 3D view shows" });
  return (
    within(group)
      .getAllByRole("button")
      .find((button) => button.getAttribute("aria-pressed") === "true")?.textContent ?? null
  );
}

/** The style of the swatch beside a legend entry. */
function swatch(entry: string): CSSStyleDeclaration {
  const item = screen.getByText(entry);
  return (item.firstElementChild!.firstElementChild as HTMLElement).style;
}

/** A colour as the browser writes it back in a style. */
function css(color: string): string {
  const element = document.createElement("span");
  element.style.color = color;
  return element.style.color;
}
