import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { SMALL_COMPLEX } from "@/lib/test-complexes";

import { createScene, type SceneOptions } from "./scene";

type FakeAtom = { x: number; y: number; z: number };

/** Just enough of 3Dmol to see what the scene draws. */
function fakeThreeDmol() {
  const models: { atoms: FakeAtom[]; styles: unknown[] }[] = [];
  let view = [0, 0, 0, 100, 0, 0, 0, 1];
  const viewer = {
    addModel: vi.fn(() => {
      const model = {
        atoms: [] as FakeAtom[],
        styles: [] as unknown[],
        addAtoms: (atoms: FakeAtom[]) => model.atoms.push(...atoms.map((atom) => ({ ...atom }))),
        assignBonds: vi.fn(),
        selectedAtoms: () => model.atoms,
        setStyle: (_selection: unknown, style: unknown) => model.styles.push(style),
      };
      models.push(model);
      return model;
    }),
    setStyle: vi.fn(),
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
    render: vi.fn(),
    resize: vi.fn(),
    clear: vi.fn(),
  };
  const lib = { createViewer: vi.fn(() => viewer) } as unknown as typeof import("3dmol");
  return { lib, viewer, models };
}

const options: SceneOptions = { mode: "site", dark: true, reduceMotion: false };

let frames: FrameRequestCallback[] = [];

beforeEach(() => {
  frames = [];
  vi.stubGlobal("requestAnimationFrame", (callback: FrameRequestCallback) => {
    frames.push(callback);
    return frames.length;
  });
  vi.stubGlobal("cancelAnimationFrame", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Runs the animation frames until none is left, `ms` apart. */
function runFrames(ms: number) {
  let now = performance.now();
  while (frames.length > 0) {
    now += ms;
    frames.shift()!(now);
  }
}

describe("createScene", () => {
  it("shows the binding site with its hydrogen bonds labelled, and turns slowly", () => {
    const { lib, viewer } = fakeThreeDmol();

    createScene(
      lib,
      document.createElement("div"),
      { kind: "complex", complex: SMALL_COMPLEX },
      options,
    );

    expect(viewer.addCylinder).toHaveBeenCalledTimes(2);
    expect(viewer.addLabel.mock.calls.map(([label]) => label)).toEqual(["Glu2", "Thr7A"]);
    expect(viewer.spin).toHaveBeenLastCalledWith("y", expect.any(Number), true);
  });

  it("shows the drug alone in Molecule mode", () => {
    const { lib, viewer } = fakeThreeDmol();
    const scene = createScene(
      lib,
      document.createElement("div"),
      { kind: "complex", complex: SMALL_COMPLEX },
      options,
    );
    viewer.addCylinder.mockClear();

    scene.setMode("molecule", true);

    expect(viewer.removeAllShapes).toHaveBeenCalled();
    expect(viewer.addCylinder).not.toHaveBeenCalled();
    expect(frames).toHaveLength(0);
  });

  it("brings the drug into the pocket with the camera on it, then draws the bonds", () => {
    const { lib, viewer, models } = fakeThreeDmol();
    const scene = createScene(
      lib,
      document.createElement("div"),
      { kind: "complex", complex: SMALL_COMPLEX },
      { ...options, mode: "molecule" },
    );
    const drug = models[1].atoms;

    scene.setMode("site", true);
    frames.shift()!(performance.now());
    const [x, y, z] = viewer.getView();
    const center = centerOf(drug);

    expect(center.x).toBeGreaterThan(11 + 10);
    expect([x, y, z]).toEqual([-center.x, -center.y, -center.z]);
    expect(viewer.addCylinder).not.toHaveBeenCalled();

    runFrames(100);

    expect(drug.map((atom) => Math.round(atom.x))).toEqual([10, 11, 12]);
    expect(viewer.addCylinder).toHaveBeenCalledTimes(2);
  });

  it("doesn't animate or turn when the system asks for reduced motion", () => {
    const { lib, viewer } = fakeThreeDmol();
    const scene = createScene(
      lib,
      document.createElement("div"),
      { kind: "complex", complex: SMALL_COMPLEX },
      { ...options, reduceMotion: true },
    );

    scene.replay();

    expect(frames).toHaveLength(0);
    expect(viewer.spin).not.toHaveBeenCalledWith("y", expect.anything(), true);
    expect(viewer.addCylinder).toHaveBeenCalledTimes(4);
  });

  it("draws a molecule from its SDF and frees the canvas when closed", () => {
    const { lib, viewer } = fakeThreeDmol();
    const element = document.createElement("div");
    element.append(document.createElement("canvas"));
    const scene = createScene(lib, element, { kind: "molecule", sdf: "1983\n$$$$\n" }, options);

    expect(viewer.addModel).toHaveBeenCalledWith("1983\n$$$$\n", "sdf");

    scene.dispose();

    expect(viewer.clear).toHaveBeenCalled();
    expect(element.querySelector("canvas")).toBeNull();
  });

  it("stops turning when the user grabs the view", () => {
    const { lib, viewer } = fakeThreeDmol();
    const element = document.createElement("div");
    createScene(lib, element, { kind: "molecule", sdf: "1983\n$$$$\n" }, options);

    element.dispatchEvent(new Event("pointerdown"));

    expect(viewer.spin).toHaveBeenLastCalledWith(false);
  });
});

function centerOf(atoms: FakeAtom[]) {
  const sum = atoms.reduce((s, a) => ({ x: s.x + a.x, y: s.y + a.y, z: s.z + a.z }), {
    x: 0,
    y: 0,
    z: 0,
  });
  return { x: sum.x / atoms.length, y: sum.y / atoms.length, z: sum.z / atoms.length };
}
