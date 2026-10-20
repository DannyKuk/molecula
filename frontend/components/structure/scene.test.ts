import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { Complex } from "@/lib/api";
import { METAL_COMPLEX, SMALL_COMPLEX } from "@/lib/test-complexes";

import { COLORS, createScene, type SceneOptions } from "./scene";

type FakeAtom = {
  x: number;
  y: number;
  z: number;
  index?: number;
  elem?: string;
  chain?: string;
  resi?: number;
  style?: object;
};
type Selection = {
  predicate?: (atom: FakeAtom) => boolean;
  or?: { chain?: string; resi?: number }[];
};
type Line = { start: Point; end: Point; color: string };
type Label = { text: string; opacity: number };
type Point = { x: number; y: number; z: number };

/** Just enough of 3Dmol to see what the scene draws. `sdfAtoms` are what a molecule's SDF holds.
 * `lines` and `labels` hold what is on screen now. Of the `or` selections, only residues by chain
 * and number select atoms. */
function fakeThreeDmol(sdfAtoms: FakeAtom[] = []) {
  const models: {
    atoms: FakeAtom[];
    setStyle: (selection: Selection, style: object, add?: boolean) => void;
  }[] = [];
  const lines = new Set<Line>();
  const labels = new Set<Label>();
  let view = [0, 0, 0, 100, 0, 0, 0, 1];
  const selects = (selection: Selection, atom: FakeAtom) => {
    if (selection.predicate) return selection.predicate(atom);
    if (!selection.or) return true;
    return selection.or.some((part) => part.chain === atom.chain && part.resi === atom.resi);
  };
  const viewer = {
    addModel: vi.fn((sdf?: string) => {
      const model = {
        atoms: sdf ? sdfAtoms.map((atom) => ({ ...atom })) : ([] as FakeAtom[]),
        addAtoms: (atoms: FakeAtom[]) => model.atoms.push(...atoms.map((atom) => ({ ...atom }))),
        assignBonds: vi.fn(),
        selectedAtoms: () => model.atoms,
        setStyle: (selection: Selection, style: object, add = false) => {
          for (const atom of model.atoms) {
            if (selects(selection, atom)) atom.style = add ? { ...atom.style, ...style } : style;
          }
        },
      };
      models.push(model);
      return model;
    }),
    addCylinder: vi.fn((line: Line) => {
      lines.add(line);
      return line;
    }),
    removeShape: vi.fn((line: Line) => lines.delete(line)),
    addLabel: vi.fn((text: string, spec: { fontOpacity?: number }) => {
      const label = { text, opacity: spec.fontOpacity ?? 1 };
      labels.add(label);
      return label;
    }),
    removeLabel: vi.fn((label: Label) => labels.delete(label)),
    removeAllShapes: vi.fn(() => lines.clear()),
    removeAllLabels: vi.fn(() => labels.clear()),
    zoomTo: vi.fn(),
    zoom: vi.fn((factor: number) => {
      view = [...view.slice(0, 3), 100 / factor, ...view.slice(4)];
    }),
    getView: vi.fn(() => view),
    setView: vi.fn((next: number[]) => {
      view = next;
    }),
    spin: vi.fn(),
    setSlab: vi.fn(),
    render: vi.fn(),
    resize: vi.fn(),
    clear: vi.fn(),
  };
  const lib = { createViewer: vi.fn(() => viewer) } as unknown as typeof import("3dmol");
  return { lib, viewer, models, lines, labels };
}

const drawn = (atoms: FakeAtom[]) => atoms.filter((atom) => Object.keys(atom.style ?? {}).length);

/** The element colours an atom's sticks are drawn in. */
const colorMap = (atom: FakeAtom) =>
  (atom.style as { stick: { colorscheme: { map: object } } }).stick.colorscheme.map;

const SCREEN_ELEMENTS = {
  H: "#ffffff",
  Cl: "#f472b6",
  F: "#34d399",
  I: "#a970ff",
  N: "#8ea6ff",
  O: "#ff6b5e",
  P: "#ffa64d",
  S: "#f2d16b",
};

const options: SceneOptions = {
  mode: "site",
  colors: COLORS.screenDark,
  reduceMotion: false,
};

const frames = new Map<number, FrameRequestCallback>();
let lastFrame = 0;
let now = 0;

beforeEach(() => {
  frames.clear();
  now = 0;
  vi.spyOn(performance, "now").mockImplementation(() => now);
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    frames.set(++lastFrame, callback);
    return lastFrame;
  });
  vi.stubGlobal("cancelAnimationFrame", (id: number) => frames.delete(id));
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

/** Runs the animation frames `ms` apart, until `until` ms from now or until none is left. */
function runFrames(ms = 100, until = Infinity) {
  const end = now + until;
  while (frames.size > 0 && now < end) {
    const [id, callback] = frames.entries().next().value!;
    frames.delete(id);
    now += ms;
    callback(now);
  }
}

function complexScene(sceneOptions: Partial<SceneOptions> = {}, complex: Complex = SMALL_COMPLEX) {
  const fake = fakeThreeDmol();
  const element = document.createElement("div");
  const scene = createScene(
    fake.lib,
    element,
    { kind: "complex", complex },
    { ...options, ...sceneOptions },
  );
  const [protein, drug, metals, cofactors] = fake.models;
  const grab = () => element.firstChild!.dispatchEvent(new Event("pointerdown"));
  return {
    ...fake,
    scene,
    protein: protein.atoms,
    drug: drug.atoms,
    metals: metals.atoms,
    cofactors: cofactors.atoms,
    grab,
  };
}

describe("createScene", () => {
  it("shows the binding site with its hydrogen bonds labelled, and turns slowly", () => {
    const { viewer } = complexScene();

    expect(viewer.addCylinder).toHaveBeenCalledTimes(2);
    expect(viewer.addLabel.mock.calls.map(([label]) => label)).toEqual(["Glu2", "Thr7A"]);
    expect(viewer.spin).toHaveBeenLastCalledWith("y", expect.any(Number));
  });

  it("colours the drug's carbons lime in every view, and the pocket's grey", () => {
    const { scene, drug, models } = complexScene();
    const elements = SCREEN_ELEMENTS;
    const pocketStyle = vi.spyOn(models[0], "setStyle");

    expect(colorMap(drug[0])).toEqual({ ...elements, C: "#c6f432" });

    scene.setMode("molecule", false);
    expect(colorMap(drug[0])).toEqual({ ...elements, C: "#c6f432" });

    scene.setMode("protein", false);
    expect(colorMap(drug[0])).toEqual({ ...elements, C: "#c6f432" });

    scene.setMode("site", false);
    expect(pocketStyle).toHaveBeenCalledWith(
      { or: expect.any(Array) },
      {
        stick: { radius: 0.12, colorscheme: { prop: "elem", map: { ...elements, C: "#7a8088" } } },
      },
      true,
    );
  });

  it("draws on the dark screen's colour in both themes", () => {
    expect(complexScene().lib.createViewer).toHaveBeenCalledWith(expect.anything(), {
      backgroundColor: "#0f1012",
      antialias: true,
    });
    expect(complexScene({ colors: COLORS.screen }).lib.createViewer).toHaveBeenCalledWith(
      expect.anything(),
      { backgroundColor: "#1b1d20", antialias: true },
    );
  });

  it("colours the carbons of a drug without a complex lime too", () => {
    const { lib, models } = fakeThreeDmol([{ x: 0, y: 0, z: 0, elem: "C" }]);
    createScene(lib, document.createElement("div"), sdf, options);

    expect(colorMap(models[0].atoms[0])).toEqual({ ...SCREEN_ELEMENTS, C: "#c6f432" });
  });

  it("draws chlorine pink and fluorine green, apart from the drug's lime carbons and sulfur's yellow", () => {
    const { lib, models } = fakeThreeDmol([{ x: 0, y: 0, z: 0, elem: "Cl" }]);
    createScene(lib, document.createElement("div"), sdf, options);
    const colors = colorMap(models[0].atoms[0]) as Record<string, string>;

    expect([colors.Cl, colors.F]).toEqual(["#f472b6", "#34d399"]);
    expect(new Set([colors.C, colors.Cl, colors.F, colors.S]).size).toBe(4);
  });

  it("draws the printed picture in 3Dmol's green carbons and element colours on a light background, in every view", () => {
    const paper = {
      H: "#b0b0b0",
      Cl: "#db2777",
      F: "#34d399",
      I: "#a020f0",
      N: "#8f8fff",
      O: "#f00000",
      P: "#ffa500",
      S: "#ffc832",
      C: "#00ff00",
    };
    const { lib, viewer, drug, scene } = complexScene({ colors: COLORS.paper });
    const lineColors = viewer.addCylinder.mock.calls.map(
      ([line]) => (line as { color: string }).color,
    );

    expect(lib.createViewer).toHaveBeenCalledWith(expect.anything(), {
      backgroundColor: "#f2f2ee",
      antialias: true,
    });
    expect(colorMap(drug[0])).toEqual(paper);
    expect(lineColors).toEqual(["#d97706", "#d97706"]);

    scene.setMode("molecule", false);
    expect(colorMap(drug[0])).toEqual(paper);
  });

  it("shows the drug alone in Molecule mode", () => {
    const { scene, viewer } = complexScene();
    viewer.addCylinder.mockClear();

    scene.setMode("molecule", true);

    expect(viewer.removeAllShapes).toHaveBeenCalled();
    expect(viewer.addCylinder).not.toHaveBeenCalled();
    expect(frames.size).toBe(0);
  });

  it("builds the drug up outside the pocket, grows the backbone, docks it and adds the bonds one by one", () => {
    const { scene, viewer, protein, drug, lines, labels } = complexScene();

    scene.replay();
    expect(lines.size).toBe(0);
    expect(drawn(drug)).toHaveLength(0);
    expect(drawn(protein)).toHaveLength(0);
    expect(centerOf(drug).x).toBeGreaterThan(11 + 10);

    runFrames(100, 100);
    expect(drawn(drug).length).toBeGreaterThan(0);
    expect(drawn(drug).length).toBeLessThan(3);

    runFrames(100, 1400);
    expect(drawn(drug)).toHaveLength(3);
    expect(drawn(protein).length).toBeGreaterThan(0);
    expect(drawn(protein).length).toBeLessThan(5);
    const [x, y, z] = viewer.getView();
    expect([x, y, z]).toEqual([-centerOf(drug).x, -centerOf(drug).y, -centerOf(drug).z]);

    runFrames(100, 4800);
    expect(drug.map((atom) => Math.round(atom.x))).toEqual([10, 11, 12]);
    expect(lines.size).toBe(1);
    expect(viewer.spin).not.toHaveBeenLastCalledWith("y", expect.anything());

    runFrames();
    expect(lines.size).toBe(2);
    expect([...labels]).toEqual([
      { text: "Glu2", opacity: 1 },
      { text: "Thr7A", opacity: 1 },
    ]);
    expect(drawn(protein).map((atom) => atom.resi)).toEqual([2, 2, 7]);
    expect(viewer.spin).toHaveBeenLastCalledWith("y", expect.any(Number));
  });

  it("grows the pocket in around the drug, nearest first, while it docks, then draws each bond out from the drug before its label fades in", () => {
    const { scene, protein, drug, lines, labels } = complexScene();
    const pocketShown = () =>
      drawn(protein)
        .filter((atom) => "stick" in atom.style!)
        .map((atom) => atom.resi);
    const awayFromPose = () =>
      Math.hypot(centerOf(drug).x - 11, centerOf(drug).y, centerOf(drug).z);
    const glu2Line = () => [...lines].find((line) => line.end.x === 10);
    const seen = { nearestOnly: false, lineWithoutLabel: false, fadingLabel: false };

    scene.replay();
    while (frames.size > 0) {
      runFrames(20, 20);
      if (pocketShown().join() === "2,2" && awayFromPose() > 0.01) seen.nearestOnly = true;
      const line = glu2Line();
      if (line && line.start.x > 8 && ![...labels].some((label) => label.text === "Glu2")) {
        seen.lineWithoutLabel = true;
      }
      if ([...labels].some((label) => label.opacity > 0 && label.opacity < 1)) {
        seen.fadingLabel = true;
      }
    }

    expect(seen).toEqual({ nearestOnly: true, lineWithoutLabel: true, fadingLabel: true });
    expect(glu2Line()).toEqual(
      expect.objectContaining({ start: { x: 8, y: 0, z: 0 }, end: { x: 10, y: 0, z: 0 } }),
    );
  });

  it("keeps the backbone at the end in Whole protein", () => {
    const { scene, protein } = complexScene({ mode: "protein" });

    scene.replay();
    runFrames();

    expect(drawn(protein)).toHaveLength(5);
  });

  it("only builds the drug up in Molecule mode", () => {
    const { scene, viewer, protein, drug } = complexScene({ mode: "molecule" });

    scene.replay();
    expect(drawn(drug)).toHaveLength(0);
    runFrames();

    expect(drawn(drug)).toHaveLength(3);
    expect(drawn(protein)).toHaveLength(0);
    expect(viewer.addCylinder).not.toHaveBeenCalled();
    expect(centerOf(drug).x).toBe(11);
  });

  it("docks the drug without building it up again when leaving Molecule mode", () => {
    const { scene, viewer, drug, lines } = complexScene({ mode: "molecule" });

    scene.setMode("site", true);
    runFrames(100, 100);

    expect(drawn(drug)).toHaveLength(3);
    expect(centerOf(drug).x).toBeGreaterThan(11 + 10);
    expect(viewer.addCylinder).not.toHaveBeenCalled();

    runFrames();
    expect(drug.map((atom) => Math.round(atom.x))).toEqual([10, 11, 12]);
    expect(lines.size).toBe(2);
  });

  it("jumps to the end when the user grabs the view while the sequence plays", () => {
    const { scene, viewer, drug, grab } = complexScene();
    viewer.addCylinder.mockClear();
    scene.replay();
    runFrames(100, 2000);

    grab();

    expect(frames.size).toBe(0);
    expect(drawn(drug)).toHaveLength(3);
    expect(drug.map((atom) => Math.round(atom.x))).toEqual([10, 11, 12]);
    expect(viewer.addCylinder).toHaveBeenCalledTimes(2);
    expect(viewer.spin).toHaveBeenLastCalledWith(false);
  });

  it("draws the whole pocket and every bond in full when the user grabs the view while a bond grows", () => {
    const { scene, protein, lines, labels, grab } = complexScene();
    scene.replay();
    while (frames.size > 0 && lines.size === 0) runFrames(20, 20);
    runFrames(20, 100);

    grab();

    expect(frames.size).toBe(0);
    expect(drawn(protein).map((atom) => atom.resi)).toEqual([2, 2, 7]);
    expect([...lines].map(({ start, end }) => [start.x, end.x])).toEqual([
      [8, 10],
      [12, 12],
    ]);
    expect([...labels].map((label) => label.opacity)).toEqual([1, 1]);
  });

  it("jumps to the end on Reset while the sequence plays, and turns again", () => {
    const { scene, viewer, drug } = complexScene();
    scene.replay();
    runFrames(100, 300);

    scene.reset();

    expect(frames.size).toBe(0);
    expect(drawn(drug)).toHaveLength(3);
    expect(viewer.spin).toHaveBeenLastCalledWith("y", expect.any(Number));
  });

  it("doesn't animate or turn when the system asks for reduced motion", () => {
    const { scene, viewer } = complexScene({ reduceMotion: true });

    scene.replay();
    scene.setMode("protein", true);

    expect(frames.size).toBe(0);
    expect(viewer.spin).not.toHaveBeenCalledWith("y", expect.anything());
    expect(viewer.addCylinder).toHaveBeenCalledTimes(6);
  });

  it("builds a molecule up atom by atom, then turns", () => {
    const sdfAtoms = [
      { x: 0, y: 0, z: 0, index: 0, elem: "C", bonds: [1] },
      { x: 1, y: 0, z: 0, index: 1, elem: "O", bonds: [0] },
    ];
    const { lib, viewer, models } = fakeThreeDmol(sdfAtoms);
    const scene = createScene(lib, document.createElement("div"), sdf, options);
    const atoms = models[0].atoms;

    scene.replay();
    expect(drawn(atoms)).toHaveLength(0);
    expect(scene.camera()).toBeNull();

    runFrames(50, 50);
    expect(drawn(atoms)).toHaveLength(1);
    expect(viewer.spin).toHaveBeenLastCalledWith(false);

    runFrames();
    expect(drawn(atoms)).toHaveLength(2);
    expect(viewer.spin).toHaveBeenLastCalledWith("y", expect.any(Number));
    expect(scene.camera()).not.toBeNull();
  });

  it("shows a molecule whole when the user grabs it while it builds itself up", () => {
    const sdfAtoms = [
      { x: 0, y: 0, z: 0, index: 0, elem: "C", bonds: [1] },
      { x: 1, y: 0, z: 0, index: 1, elem: "O", bonds: [0] },
    ];
    const { lib, viewer, models } = fakeThreeDmol(sdfAtoms);
    const element = document.createElement("div");
    const scene = createScene(lib, element, sdf, options);
    scene.replay();

    element.firstChild!.dispatchEvent(new Event("pointerdown"));

    expect(frames.size).toBe(0);
    expect(drawn(models[0].atoms)).toHaveLength(2);
    expect(viewer.spin).toHaveBeenLastCalledWith(false);
  });

  it("draws a molecule in a box of its own and removes the box when closed", () => {
    const { lib, viewer } = fakeThreeDmol();
    const element = document.createElement("div");
    const scene = createScene(lib, element, sdf, options);

    expect(viewer.addModel).toHaveBeenCalledWith("1983\n$$$$\n", "sdf");
    expect(lib.createViewer).toHaveBeenCalledWith(element.firstChild, expect.anything());

    scene.dispose();

    expect(viewer.clear).toHaveBeenCalled();
    expect(element.childElementCount).toBe(0);
  });

  it("stops the sequence when the view is closed", () => {
    const { scene } = complexScene();
    scene.replay();

    scene.dispose();

    expect(frames.size).toBe(0);
  });

  it("stops turning when the user grabs the view, until Reset", () => {
    const { lib, viewer } = fakeThreeDmol();
    const element = document.createElement("div");
    const scene = createScene(lib, element, sdf, options);

    element.firstChild!.dispatchEvent(new Event("pointerdown"));
    expect(viewer.spin).toHaveBeenLastCalledWith(false);

    scene.reset();
    expect(viewer.spin).toHaveBeenLastCalledWith("y", expect.any(Number));
  });

  it("stops turning while off screen", () => {
    const { lib, viewer } = fakeThreeDmol();
    const scene = createScene(lib, document.createElement("div"), sdf, options);

    scene.setOnScreen(false);
    expect(viewer.spin).toHaveBeenLastCalledWith(false);

    scene.setOnScreen(true);
    expect(viewer.spin).toHaveBeenLastCalledWith("y", expect.any(Number));
  });

  it("builds a view again where its camera was, and still if the user held it", () => {
    const camera = { view: [1, 2, 3, 40, 0, 0, 0, 1], grabbed: true };

    const { scene, viewer } = complexScene({ camera });

    expect(viewer.getView()).toEqual(camera.view);
    expect(viewer.spin).toHaveBeenLastCalledWith(false);
    expect(scene.camera()).toEqual(camera);
  });

  it("has no camera to keep while the sequence plays", () => {
    const { scene } = complexScene({ mode: "molecule" });

    scene.setMode("site", true);
    expect(scene.camera()).toBeNull();

    runFrames();
    expect(scene.camera()).toEqual({ view: expect.any(Array), grabbed: false });
  });

  it("plays the sequence with the camera on the drug after an earlier grab", () => {
    const { scene, viewer, drug, grab } = complexScene();
    grab();

    scene.replay();
    runFrames(100, 4000);
    const moving = centerOf(drug);

    expect(viewer.getView().slice(0, 3)).toEqual([-moving.x, -moving.y, -moving.z]);

    runFrames();
    const docked = centerOf(drug);

    expect(viewer.getView().slice(0, 3)).toEqual([-docked.x, -docked.y, -docked.z]);
    expect(viewer.spin).toHaveBeenLastCalledWith("y", expect.any(Number));
  });
});

describe("createScene with metals and cofactors", () => {
  const metalScene = (sceneOptions: Partial<SceneOptions> = {}) =>
    complexScene(sceneOptions, METAL_COMPLEX);
  type Viewer = ReturnType<typeof fakeThreeDmol>["viewer"];
  const labels = (viewer: Viewer) => viewer.addLabel.mock.calls.map(([label]) => label);
  const lineColors = (viewer: Viewer) =>
    viewer.addCylinder.mock.calls.map(([line]) => (line as { color: string }).color);
  const metalBond = "#c084fc";
  const hydrogenBond = "#ff7a3d";

  it("shows the metal ions and cofactors, with the metal bonds before the hydrogen bonds", () => {
    const { viewer, metals, cofactors } = metalScene();

    expect(metals[0].style).toEqual({ sphere: { radius: 0.7, color: metalBond } });
    expect(cofactors[0].style).toEqual(
      expect.objectContaining({ sphere: { radius: 0.7, color: metalBond } }),
    );
    expect(cofactors.map((atom) => Object.keys(atom.style!))).toEqual([
      ["stick", "sphere"],
      ["stick"],
      ["stick"],
    ]);
    expect(labels(viewer)).toEqual(["Zn", "Fe", "Glu2", "Thr7A"]);
    expect(lineColors(viewer)).toEqual([metalBond, metalBond, hydrogenBond, hydrogenBond]);
  });

  it("frames the binding site on the drug and the metals it binds through", () => {
    const framedSites = (viewer: Viewer) =>
      viewer.zoomTo.mock.calls.filter(([selection]) => selection && "or" in selection);

    expect(framedSites(metalScene().viewer).length).toBeGreaterThan(0);
    expect(framedSites(metalScene({ mode: "molecule" }).viewer)).toEqual([]);
    expect(framedSites(complexScene().viewer)).toEqual([]);
  });

  it("adds nothing for a complex without metals or cofactors", () => {
    const { viewer, metals, cofactors } = complexScene();

    expect(metals).toEqual([]);
    expect(cofactors).toEqual([]);
    expect(labels(viewer)).toEqual(["Glu2", "Thr7A"]);
    expect(lineColors(viewer)).toEqual([hydrogenBond, hydrogenBond]);
  });

  it("hides them in Molecule mode", () => {
    const { scene, viewer, metals, cofactors } = metalScene();
    viewer.addCylinder.mockClear();
    viewer.addLabel.mockClear();

    scene.setMode("molecule", false);

    expect(drawn(metals)).toHaveLength(0);
    expect(drawn(cofactors)).toHaveLength(0);
    expect(viewer.addCylinder).not.toHaveBeenCalled();
    expect(viewer.addLabel).not.toHaveBeenCalled();
  });

  it("shows them while the backbone grows, before the drug docks, and adds their bonds first", () => {
    const { scene, viewer, drug, metals, cofactors, lines, labels: shown } = metalScene();
    const shownColors = () => [...lines].map((line) => line.color);
    const shownLabels = () => [...shown].map((label) => label.text);
    viewer.addCylinder.mockClear();
    viewer.addLabel.mockClear();

    scene.replay();
    runFrames(100, 700);
    expect(drawn(metals)).toHaveLength(0);
    expect(drawn(cofactors)).toHaveLength(0);

    runFrames(100, 300);
    expect(drawn(metals)).toHaveLength(1);
    expect(drawn(cofactors)).toHaveLength(3);
    expect(labels(viewer)).toEqual(["Zn", "Fe"]);
    expect(centerOf(drug).x).toBeGreaterThan(11 + 10);
    expect(viewer.addCylinder).not.toHaveBeenCalled();

    runFrames(100, 5300);
    expect(shownColors()).toEqual([metalBond]);

    runFrames();
    expect(shownColors()).toEqual([metalBond, metalBond, hydrogenBond, hydrogenBond]);
    expect(shownLabels()).toEqual(["Zn", "Fe", "Glu2", "Thr7A"]);
  });

  it("shows them with their bonds when the user grabs the view while the sequence plays", () => {
    const { scene, viewer, metals, cofactors, grab } = metalScene();
    scene.replay();
    runFrames(100, 300);
    viewer.addCylinder.mockClear();
    viewer.addLabel.mockClear();

    grab();

    expect(frames.size).toBe(0);
    expect(drawn(metals)).toHaveLength(1);
    expect(drawn(cofactors)).toHaveLength(3);
    expect(lineColors(viewer)).toEqual([metalBond, metalBond, hydrogenBond, hydrogenBond]);
    expect(labels(viewer)).toEqual(["Zn", "Fe", "Glu2", "Thr7A"]);
  });

  it("shows them without a sequence when the system asks for reduced motion", () => {
    const { scene, viewer, metals } = metalScene({ reduceMotion: true });
    viewer.addCylinder.mockClear();

    scene.replay();

    expect(frames.size).toBe(0);
    expect(drawn(metals)).toHaveLength(1);
    expect(lineColors(viewer)).toEqual([metalBond, metalBond, hydrogenBond, hydrogenBond]);
  });

  it("shows them when a view is built again with its camera", () => {
    const camera = { view: [1, 2, 3, 40, 0, 0, 0, 1], grabbed: false };

    const { viewer, metals, cofactors } = metalScene({ camera });

    expect(drawn(metals)).toHaveLength(1);
    expect(drawn(cofactors)).toHaveLength(3);
    expect(lineColors(viewer)).toEqual([metalBond, metalBond, hydrogenBond, hydrogenBond]);
    expect(viewer.getView()).toEqual(camera.view);
  });

  it("draws the cofactors in cyan", () => {
    const { cofactors } = metalScene();

    expect(cofactors[1].style).toEqual({ stick: { radius: 0.1, color: "#22d3ee" } });
  });
});

const sdf = { kind: "molecule", sdf: "1983\n$$$$\n" } as const;

function centerOf(atoms: FakeAtom[]) {
  const sum = atoms.reduce((s, a) => ({ x: s.x + a.x, y: s.y + a.y, z: s.z + a.z }), {
    x: 0,
    y: 0,
    z: 0,
  });
  return { x: sum.x / atoms.length, y: sum.y / atoms.length, z: sum.z / atoms.length };
}
