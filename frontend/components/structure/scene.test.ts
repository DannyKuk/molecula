import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SMALL_COMPLEX } from "@/lib/test-complexes";

import { createScene, type SceneOptions } from "./scene";

type FakeAtom = { x: number; y: number; z: number; index?: number; style?: object };
type Selection = { predicate?: (atom: FakeAtom) => boolean; or?: unknown };

/** Just enough of 3Dmol to see what the scene draws. `sdfAtoms` are what a molecule's SDF holds. */
function fakeThreeDmol(sdfAtoms: FakeAtom[] = []) {
  const models: { atoms: FakeAtom[] }[] = [];
  let view = [0, 0, 0, 100, 0, 0, 0, 1];
  const selects = (selection: Selection, atom: FakeAtom) =>
    selection.predicate ? selection.predicate(atom) : !selection.or;
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
    addCylinder: vi.fn(),
    addLabel: vi.fn(),
    removeAllShapes: vi.fn(),
    removeAllLabels: vi.fn(),
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
  return { lib, viewer, models };
}

const drawn = (atoms: FakeAtom[]) => atoms.filter((atom) => Object.keys(atom.style ?? {}).length);

const options: SceneOptions = { mode: "site", dark: true, reduceMotion: false };

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

function complexScene(sceneOptions: Partial<SceneOptions> = {}) {
  const fake = fakeThreeDmol();
  const element = document.createElement("div");
  const scene = createScene(
    fake.lib,
    element,
    { kind: "complex", complex: SMALL_COMPLEX },
    { ...options, ...sceneOptions },
  );
  const [protein, drug] = fake.models;
  const grab = () => element.firstChild!.dispatchEvent(new Event("pointerdown"));
  return { ...fake, scene, protein: protein.atoms, drug: drug.atoms, grab };
}

describe("createScene", () => {
  it("shows the binding site with its hydrogen bonds labelled, and turns slowly", () => {
    const { viewer } = complexScene();

    expect(viewer.addCylinder).toHaveBeenCalledTimes(2);
    expect(viewer.addLabel.mock.calls.map(([label]) => label)).toEqual(["Glu2", "Thr7A"]);
    expect(viewer.spin).toHaveBeenLastCalledWith("y", expect.any(Number));
  });

  it("colours the drug's carbons green next to the protein, and by element on its own", () => {
    const { scene, drug } = complexScene();
    const carbons = () => (drug[0].style as { stick: { colorscheme?: string } }).stick.colorscheme;

    expect(carbons()).toBe("greenCarbon");

    scene.setMode("molecule", false);
    expect(carbons()).toBe("default");
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
    const { scene, viewer, protein, drug } = complexScene();
    viewer.addCylinder.mockClear();

    scene.replay();
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
    expect(viewer.addCylinder).toHaveBeenCalledTimes(1);
    expect(viewer.spin).not.toHaveBeenLastCalledWith("y", expect.anything());

    runFrames();
    expect(viewer.addCylinder).toHaveBeenCalledTimes(2);
    expect(drawn(protein).map((atom) => atom.index)).toEqual([]);
    expect(viewer.spin).toHaveBeenLastCalledWith("y", expect.any(Number));
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
    const { scene, viewer, drug } = complexScene({ mode: "molecule" });

    scene.setMode("site", true);
    runFrames(100, 100);

    expect(drawn(drug)).toHaveLength(3);
    expect(centerOf(drug).x).toBeGreaterThan(11 + 10);
    expect(viewer.addCylinder).not.toHaveBeenCalled();

    runFrames();
    expect(drug.map((atom) => Math.round(atom.x))).toEqual([10, 11, 12]);
    expect(viewer.addCylinder).toHaveBeenCalledTimes(2);
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

const sdf = { kind: "molecule", sdf: "1983\n$$$$\n" } as const;

function centerOf(atoms: FakeAtom[]) {
  const sum = atoms.reduce((s, a) => ({ x: s.x + a.x, y: s.y + a.y, z: s.z + a.z }), {
    x: 0,
    y: 0,
    z: 0,
  });
  return { x: sum.x / atoms.length, y: sum.y / atoms.length, z: sum.z / atoms.length };
}
