import type { AtomSpec, GLModel, GLViewer } from "3dmol";

import type { Complex } from "@/lib/api";
import {
  approachDirection,
  assemblyDuration,
  assemblyFrame,
  assemblyOrder,
  centroid,
  cofactorAtoms,
  coordinationBonds,
  dockingPose,
  easeInOut,
  hydrogenBonds,
  isMetal,
  ligandAtoms,
  metalAtoms,
  metalLabels,
  pocketSelection,
  proteinAtoms,
  type CoordinationLine,
  type HydrogenBondLine,
  type MetalLabel,
  type Point,
} from "@/lib/complex-scene";

type ThreeDmol = typeof import("3dmol");

/** What the 3D view shows: the drug alone, the drug in its pocket, or that plus the backbone. */
export type ViewMode = "molecule" | "site" | "protein";

export type SceneData = { kind: "complex"; complex: Complex } | { kind: "molecule"; sdf: string };

/** The camera and whether the user held the view, kept to build a released view again. */
export type Camera = { view: number[]; grabbed: boolean };

export type SceneOptions = {
  mode: ViewMode;
  colors: Palette;
  reduceMotion: boolean;
  camera?: Camera;
};

export type Scene = {
  /** Switches the view; `animate` plays the binding when the pocket comes into view. */
  setMode(mode: ViewMode, animate: boolean): void;
  /** Plays the sequence again: the drug builds itself up and, in a complex, binds. */
  replay(): void;
  reset(): void;
  /** A view scrolled off screen stops turning, so the views further up the chat cost nothing. */
  setOnScreen(onScreen: boolean): void;
  /** The camera to build the view again with, or null while the sequence plays. */
  camera(): Camera | null;
  resize(): void;
  /** The view as it is drawn now, as a PNG data URL. */
  picture(): string;
  dispose(): void;
};

export type Palette = {
  background: string;
  drug: string;
  pocket: string;
  trace: string;
  traceOpacity: number;
  label: string;
  labelBackground: string;
  hbond: string;
  coordination: string;
  cofactor: string;
  /** Element colours in place of 3Dmol's; the elements left out keep 3Dmol's. */
  elements: Record<string, string>;
};

// The view is drawn on its background, not on a transparent canvas: Chrome on the owner's AMD GPU
// showed the transparent white clear colour as solid white, and 3Dmol fades distant atoms into the
// background colour.
const SCREEN: Palette = {
  background: "#1b1d20",
  drug: "#c6f432",
  pocket: "#7a8088",
  trace: "#3a3e44",
  // The backbone colour is already dim on the dark screen, so it is drawn solid.
  traceOpacity: 1,
  label: "#e6e8e3",
  labelBackground: "#2a2d31",
  hbond: "#ff7a3d",
  coordination: "#c084fc",
  cofactor: "#22d3ee",
  // 3Dmol's own nitrogen, oxygen and sulfur are too dark or too loud on the screen.
  elements: { N: "#8ea6ff", O: "#ff6b5e", S: "#f2d16b" },
};

/**
 * The colours of the view and its legend: the app's dark screen (#297), a shade darker in dark mode
 * (`--screen` in globals.css), and the light colours of the picture printed on white paper (#312),
 * with 3Dmol's green and grey carbons.
 */
export const COLORS = {
  screen: SCREEN,
  screenDark: { ...SCREEN, background: "#0f1012" },
  paper: {
    background: "#f2f2ee",
    drug: "#00ff00",
    pocket: "#c8c8c8",
    trace: "#71717a",
    traceOpacity: 0.35,
    label: "#18181b",
    labelBackground: "#ffffff",
    hbond: "#d97706",
    coordination: "#9333ea",
    cofactor: "#0e7490",
    elements: {},
  },
} satisfies Record<string, Palette>;

/** Colours by element, with `carbon` for the carbons if given, else 3Dmol's light grey. */
function byElement(elements: Record<string, string>, carbon?: string) {
  return { prop: "elem", map: carbon ? { ...elements, C: carbon } : elements };
}

// Zoomed out enough that the drug and its metals clear the title and the switch on the screen.
const ZOOM: Record<ViewMode, number> = { molecule: 0.8, site: 0.6, protein: 0.5 };
// Far enough out while the backbone grows to see the protein around the pocket.
const REVEAL_ZOOM = 0.3;

const HOLD_MS = 300;
const REVEAL_MS = 2800;
const DOCK_MS = 2600;
const CONTACT_MS = 350;
// The backbone grows and fades in steps: each one restyles the whole protein, which for the largest
// complexes (thousands of residues) is too slow to do on every frame.
const TRACE_STEPS = 20;
const FADE_STEPS = 5;
const FADE_FROM = 0.6;
const SPIN_SPEED = 0.25;
// Wider than any stored complex: `zoomTo` on the drug would otherwise clip the protein around it.
const SLAB = 500;

/** The slow turn: on once the view is settled, held while it is off screen, and stopped for good
 * when the user grabs the view, until Reset or the binding plays again. */
type Turning = { start(): void; stop(): void; release(): void };

/** The sequence playing, if any: `stop` halts it where it is, `skip` jumps to its end, which is what
 * a click or drag in the view does. */
type Playing = { current: { stop(): void; skip(): void } | null };

type Colorscheme = ReturnType<typeof byElement>;

type DrugStyle = {
  stick: { radius: number; colorscheme: Colorscheme };
  sphere: { scale: number; colorscheme: Colorscheme };
};

function moleculeStyle(colors: Palette): DrugStyle {
  const colorscheme = byElement(colors.elements);
  return { stick: { radius: 0.15, colorscheme }, sphere: { scale: 0.25, colorscheme } };
}

/** Builds the 3D view in `element`, which must already have its size. */
export function createScene(
  lib: ThreeDmol,
  element: HTMLElement,
  data: SceneData,
  options: SceneOptions,
): Scene {
  // Each scene draws into its own box: 3Dmol keeps listeners on its container after `clear()`, and
  // a disposed viewer would otherwise take over the next scene's canvas.
  const box = document.createElement("div");
  box.style.cssText = "position: absolute; inset: 0;";
  element.append(box);
  const viewer = lib.createViewer(box, {
    backgroundColor: options.colors.background,
    antialias: true,
  });
  let wanted = false;
  let onScreen = true;
  let grabbed = false;
  const playing: Playing = { current: null };
  const apply = () => {
    if (wanted && onScreen && !grabbed && !options.reduceMotion) viewer.spin("y", SPIN_SPEED);
    else viewer.spin(false);
  };
  const turning: Turning = {
    start: () => {
      wanted = true;
      apply();
    },
    stop: () => {
      wanted = false;
      apply();
    },
    release: () => {
      grabbed = false;
    },
  };
  const grab = () => {
    grabbed = true;
    playing.current?.skip();
    apply();
  };
  box.addEventListener("pointerdown", grab);
  const restore = (camera: Camera) => {
    grabbed = camera.grabbed;
    viewer.setView(camera.view);
    viewer.render();
    apply();
  };
  const common = {
    setOnScreen: (visible: boolean) => {
      onScreen = visible;
      apply();
    },
    camera: () => (playing.current ? null : { view: viewer.getView(), grabbed }),
    resize: () => {
      viewer.resize();
      viewer.render();
    },
    picture: () => viewer.pngURI(),
    dispose: () => {
      playing.current?.stop();
      box.removeEventListener("pointerdown", grab);
      viewer.spin(false);
      viewer.clear();
      releaseContext(box);
      box.remove();
    },
  };

  const scene =
    data.kind === "molecule"
      ? moleculeScene(viewer, data.sdf, options, turning, playing, common)
      : complexScene(viewer, data.complex, options, turning, playing, common);
  if (options.camera) restore(options.camera);
  return scene;
}

type Common = Pick<Scene, "setOnScreen" | "camera" | "resize" | "picture" | "dispose">;

function moleculeScene(
  viewer: GLViewer,
  sdf: string,
  options: SceneOptions,
  turning: Turning,
  playing: Playing,
  common: Common,
): Scene {
  const model = viewer.addModel(sdf, "sdf");
  const style = moleculeStyle(options.colors);
  const drug = assembly(model, style);
  const settle = () => {
    playing.current = null;
    model.setStyle({}, style);
    viewer.render();
    turning.start();
  };
  const reset = () => {
    playing.current?.stop();
    turning.release();
    viewer.zoomTo();
    viewer.setSlab(-SLAB, SLAB);
    settle();
  };
  reset();
  return {
    ...common,
    setMode: () => {},
    replay: () => {
      reset();
      if (options.reduceMotion) return;
      turning.stop();
      const show = (elapsed: number) => {
        drug.show(elapsed);
        viewer.render();
      };
      show(0);
      const stop = play(drug.duration, show, settle);
      playing.current = {
        stop,
        skip: () => {
          stop();
          settle();
        },
      };
    },
    reset,
  };
}

function complexScene(
  viewer: GLViewer,
  complex: Complex,
  options: SceneOptions,
  turning: Turning,
  playing: Playing,
  common: Common,
): Scene {
  const colors = options.colors;
  const protein = viewer.addModel();
  protein.addAtoms(proteinAtoms(complex));
  protein.assignBonds();
  const proteinSize = protein.selectedAtoms({}).length;
  const ligand = viewer.addModel();
  ligand.addAtoms(ligandAtoms(complex.ligand));
  const metals = viewer.addModel();
  metals.addAtoms(metalAtoms(complex));
  const cofactors = viewer.addModel();
  cofactors.addAtoms(cofactorAtoms(complex));
  const atoms = ligand.selectedAtoms({});
  const bound = atoms.map(({ x, y, z }) => ({ x: x!, y: y!, z: z! }));
  const center = centroid(bound);
  const approach = approachDirection(complex);
  const outside = dockingPose(bound, approach, 0);
  const pocket = pocketSelection(complex);
  let mode = options.mode;
  let ligandStyle = moleculeStyle(colors);

  const placeLigand = (positions: Point[]) => {
    atoms.forEach((atom, i) => Object.assign(atom, positions[i]));
    // Restyling makes 3Dmol rebuild the drug's geometry at the new positions.
    ligand.setStyle({}, ligandStyle);
  };

  const showTrace = (upTo: number, opacity: number) => {
    protein.setStyle({}, {});
    if (upTo === 0 || opacity === 0) return;
    protein.setStyle(
      { predicate: (atom) => atom.index! < upTo },
      { cartoon: { style: "trace", color: colors.trace, thickness: 0.3, opacity } },
    );
  };

  const showPocket = () =>
    protein.setStyle(
      pocket,
      { stick: { radius: 0.12, colorscheme: byElement(colors.elements, colors.pocket) } },
      true,
    );

  const addDashedLine = (start: Point, end: Point, color: string) =>
    viewer.addCylinder({
      start,
      end,
      radius: 0.09,
      dashed: true,
      dashLength: 0.25,
      gapLength: 0.15,
      color,
      fromCap: 1,
      toCap: 1,
    });

  const addLabel = (
    text: string,
    position: Point,
    border: string,
    alignment: "topLeft" | "center" = "topLeft",
  ) =>
    viewer.addLabel(text, {
      position,
      alignment,
      fontSize: 12,
      fontColor: colors.label,
      backgroundColor: colors.labelBackground,
      backgroundOpacity: 0.85,
      borderColor: border,
      borderThickness: 1,
      inFront: true,
    });

  const showHydrogenBond = (bond: HydrogenBondLine) => {
    addDashedLine(bond.residue, bond.ligand, colors.hbond);
    addLabel(bond.label, bond.residue, colors.hbond);
  };

  const showCoordination = (line: CoordinationLine) =>
    addDashedLine(line.metal, line.ligand, colors.coordination);

  const showMetalLabel = (metal: MetalLabel) =>
    addLabel(metal.label, metal.position, colors.coordination, "center");

  const contactLines = [
    ...coordinationBonds(complex).map((line) => () => showCoordination(line)),
    ...hydrogenBonds(complex).map((bond) => () => showHydrogenBond(bond)),
  ];

  /** The metal ions and cofactors the drug binds through: part of the site, so the drug docks onto
   * them. */
  const showBindingPartners = () => {
    // One colour for every metal, the metal bonds' violet: element colours put magnesium in the
    // drug's green and zinc in the nitrogens' blue.
    const metalStyle = { sphere: { radius: 0.7, color: colors.coordination } };
    metals.setStyle({}, metalStyle);
    cofactors.setStyle({}, { stick: { radius: 0.1, color: colors.cofactor } });
    cofactors.setStyle({ predicate: (atom) => isMetal(atom.elem) }, metalStyle, true);
    metalLabels(complex).forEach(showMetalLabel);
  };

  const hideBindingPartners = () => {
    metals.setStyle({}, {});
    cofactors.setStyle({}, {});
  };

  // 3Dmol's view is [-center x, -center y, -center z, camera distance, rotation quaternion x y z w];
  // keeping the rotation lets the camera follow the drug without turning.
  const viewAt = (target: Point, distance: number) => {
    const [, , , , ...rotation] = viewer.getView();
    return [-target.x, -target.y, -target.z, distance, ...rotation];
  };

  const distanceAt = (zoom: number) => {
    const current = viewer.getView();
    viewer.zoomTo({ model: ligand });
    viewer.zoom(zoom);
    const distance = viewer.getView()[3];
    viewer.setView(current);
    viewer.setSlab(-SLAB, SLAB);
    return distance;
  };

  const metalsInSite = metalLabels(complex).length > 0;
  const site = {
    or: [
      { model: ligand },
      { model: metals },
      { model: cofactors, predicate: (atom: AtomSpec) => isMetal(atom.elem) },
    ],
  };

  /** Where the camera ends up: on the drug, or outside Molecule mode on the drug and the metals it
   * binds through, so a metal at the drug's edge and its label stay in the frame. The drug must be
   * in its bound pose. */
  const endView = (): { target: Point; distance: number } => {
    if (mode === "molecule" || !metalsInSite) {
      return { target: center, distance: distanceAt(ZOOM[mode]) };
    }
    const current = viewer.getView();
    viewer.zoomTo(site);
    viewer.zoom(ZOOM[mode]);
    const [x, y, z, distance] = viewer.getView();
    viewer.setView(current);
    viewer.setSlab(-SLAB, SLAB);
    return { target: { x: -x, y: -y, z: -z }, distance };
  };

  const setMode = (next: ViewMode, animate: boolean) => {
    mode = next;
    const carbons = byElement(colors.elements, next === "molecule" ? undefined : colors.drug);
    ligandStyle = {
      stick: { radius: 0.2, colorscheme: carbons },
      sphere: { scale: 0.25, colorscheme: carbons },
    };
    if (animate && next !== "molecule" && !options.reduceMotion) playSequence(false);
    else settle();
  };

  let framed = false;
  const settle = () => {
    playing.current?.stop();
    playing.current = null;
    turning.stop();
    viewer.removeAllShapes();
    viewer.removeAllLabels();
    showTrace(mode === "protein" ? proteinSize : 0, colors.traceOpacity);
    if (mode !== "molecule") {
      showPocket();
      showBindingPartners();
    } else {
      hideBindingPartners();
    }
    placeLigand(bound);
    if (!framed) {
      viewer.zoomTo({ model: ligand });
      framed = true;
    }
    const { target, distance } = endView();
    viewer.setView(viewAt(target, distance));
    if (mode !== "molecule") contactLines.forEach((show) => show());
    viewer.render();
    turning.start();
  };

  /**
   * The drug builds itself up (`assemble`); outside Molecule mode it does so outside the pocket,
   * then the camera pulls back while the backbone grows and the metals and cofactors appear, the
   * drug docks with the camera on it, and the metal bonds and hydrogen bonds appear one by one. The
   * path in is an illustration; only the end pose is from the structure.
   */
  const playSequence = (assemble: boolean) => {
    playing.current?.stop();
    turning.stop();
    turning.release();
    viewer.removeAllShapes();
    viewer.removeAllLabels();
    const docks = mode !== "molecule";
    const drug = assembly(ligand, ligandStyle);
    const near = distanceAt(ZOOM.molecule);
    const far = distanceAt(REVEAL_ZOOM);
    placeLigand(bound);
    const { target, distance: end } = endView();
    const drift = { x: target.x - center.x, y: target.y - center.y, z: target.z - center.z };
    const reveal = assemble ? drug.duration + HOLD_MS : 0;
    const docking = reveal + REVEAL_MS;
    const contacts = docking + DOCK_MS;
    const duration = docks ? contacts + contactLines.length * CONTACT_MS : drug.duration;
    const fades = mode === "site";
    let traceStep = -1;
    let fadeStep = -1;
    let shownContacts = 0;
    let partnersShown = false;
    let assembled = !assemble;

    hideBindingPartners();
    if (docks) showTrace(0, 0);
    placeLigand(docks ? outside : bound);
    if (assemble) drug.show(0);
    viewer.setView(viewAt(docks ? centroid(outside) : center, near));
    viewer.render();

    const step = (elapsed: number) => {
      if (!assembled) {
        assembled = elapsed >= drug.duration;
        if (assembled) placeLigand(docks ? outside : bound);
        else drug.show(elapsed);
      }
      if (docks && !partnersShown && elapsed >= reveal) {
        partnersShown = true;
        showBindingPartners();
      }
      if (docks && elapsed >= reveal && elapsed < docking) {
        const progress = easeInOut((elapsed - reveal) / REVEAL_MS);
        const nextStep = Math.ceil(progress * TRACE_STEPS);
        if (nextStep !== traceStep) {
          traceStep = nextStep;
          showTrace(Math.round((proteinSize * traceStep) / TRACE_STEPS), colors.traceOpacity);
        }
        viewer.setView(viewAt(centroid(outside), near + (far - near) * progress));
      }
      if (docks && elapsed >= docking && elapsed < contacts) {
        const progress = (elapsed - docking) / DOCK_MS;
        const positions = dockingPose(bound, approach, progress);
        placeLigand(positions);
        const eased = easeInOut(progress);
        const docked = centroid(positions);
        const camera = {
          x: docked.x + drift.x * eased,
          y: docked.y + drift.y * eased,
          z: docked.z + drift.z * eased,
        };
        viewer.setView(viewAt(camera, far + (end - far) * eased));
        const nextFade = fades
          ? Math.ceil((Math.max(0, progress - FADE_FROM) / (1 - FADE_FROM)) * FADE_STEPS)
          : 0;
        if (nextFade !== fadeStep) {
          fadeStep = nextFade;
          showTrace(proteinSize, colors.traceOpacity * (1 - fadeStep / FADE_STEPS));
        }
      }
      if (docks && elapsed >= contacts) {
        if (shownContacts === 0) {
          placeLigand(bound);
          showTrace(fades ? 0 : proteinSize, colors.traceOpacity);
          showPocket();
          viewer.setView(viewAt(target, end));
        }
        const due = Math.min(
          contactLines.length,
          Math.floor((elapsed - contacts) / CONTACT_MS) + 1,
        );
        contactLines.slice(shownContacts, due).forEach((show) => show());
        shownContacts = Math.max(due, 1);
      }
      viewer.render();
    };

    const finish = () => {
      playing.current = null;
      step(duration);
      if (docks) contactLines.slice(shownContacts).forEach((show) => show());
      viewer.render();
      turning.start();
    };
    const stop = play(duration, step, finish);
    playing.current = { stop, skip: settle };
  };

  setMode(mode, false);
  return {
    ...common,
    setMode,
    replay: () => {
      if (options.reduceMotion) settle();
      else playSequence(true);
    },
    reset: () => {
      turning.release();
      settle();
    },
  };
}

/** The drug building itself up in `model`, atom by atom, in `style` once it is complete. */
function assembly(model: GLModel, style: DrugStyle) {
  const order = assemblyOrder(model.selectedAtoms({}));
  return {
    duration: assemblyDuration(order.length),
    show: (elapsed: number) => {
      const { bonded, growing } = assemblyFrame(order, elapsed);
      const done = new Set(bonded);
      model.setStyle({}, {});
      model.setStyle({ predicate: (atom) => done.has(atom.index!) }, style);
      for (const { atom, scale } of growing) {
        model.setStyle(
          { predicate: (other) => other.index === atom },
          { sphere: { ...style.sphere, scale: style.sphere.scale * scale } },
        );
      }
    },
  };
}

/** Calls `step` on every frame with the time since the start, then `end` after `duration` ms.
 * Returns a function that stops it. */
function play(duration: number, step: (elapsed: number) => void, end: () => void): () => void {
  const start = performance.now();
  let frame = 0;
  const tick = (now: number) => {
    if (now - start >= duration) {
      end();
      return;
    }
    step(now - start);
    frame = requestAnimationFrame(tick);
  };
  frame = requestAnimationFrame(tick);
  return () => cancelAnimationFrame(frame);
}

/** Browsers allow only a few live WebGL contexts per page, so a closed view gives its back. */
function releaseContext(element: HTMLElement) {
  const canvas = element.querySelector("canvas");
  const gl = canvas?.getContext("webgl2") ?? canvas?.getContext("webgl");
  gl?.getExtension("WEBGL_lose_context")?.loseContext();
  canvas?.remove();
}
