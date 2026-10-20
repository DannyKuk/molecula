import type { AtomSpec, GLModel, GLShape, GLViewer, Label } from "3dmol";

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
  pocketResidues,
  proteinAtoms,
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
 * which are 3Dmol's own.
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
    // 3Dmol's defaults, written out for the printed legend.
    elements: { N: "#8f8fff", O: "#f00000", S: "#ffc832" },
  },
} satisfies Record<string, Palette>;

/** Colours by element, with `carbon` for the carbons. */
function byElement(elements: Record<string, string>, carbon: string) {
  return { prop: "elem", map: { ...elements, C: carbon } };
}

// Zoomed out enough that the drug and its metals clear the title and the switch on the screen.
const ZOOM: Record<ViewMode, number> = { molecule: 0.8, site: 0.6, protein: 0.5 };
// Far enough out while the backbone grows to see the protein around the pocket.
const REVEAL_ZOOM = 0.3;

const HOLD_MS = 300;
const REVEAL_MS = 2800;
const DOCK_MS = 2600;
const CONTACT_MS = 350;
// The backbone grows, and then fades out while the pocket grows in, in steps: each one restyles the
// whole protein, which for the largest complexes (thousands of residues) is too slow to do on every
// frame.
const TRACE_STEPS = 20;
const FADE_STEPS = 5;
const FADE_FROM = 0.6;
// A bond's line reaches its residue in this share of the bond's turn; its label fades in after.
const LINE_SHARE = 0.7;
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

/** The drug in sticks and balls, with its carbons in the drug's colour in every view, so it looks
 * the same when the view switches (#318). */
function drugStyle(colors: Palette, radius: number): DrugStyle {
  const colorscheme = byElement(colors.elements, colors.drug);
  return { stick: { radius, colorscheme }, sphere: { scale: 0.25, colorscheme } };
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
  const style = drugStyle(options.colors, 0.15);
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
  const pocket = pocketResidues(complex);
  let mode = options.mode;
  const ligandStyle = drugStyle(colors, 0.2);

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

  /** The pocket residues, `amount` (0 to 1) of them, nearest the drug first. */
  const showPocket = (amount = 1) => {
    const shown = pocket.slice(0, Math.ceil(amount * pocket.length));
    if (shown.length === 0) return;
    protein.setStyle(
      { or: shown },
      { stick: { radius: 0.12, colorscheme: byElement(colors.elements, colors.pocket) } },
      true,
    );
  };

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
    opacity = 1,
  ) =>
    viewer.addLabel(text, {
      position,
      alignment,
      fontSize: 12,
      fontColor: colors.label,
      fontOpacity: opacity,
      backgroundColor: colors.labelBackground,
      backgroundOpacity: 0.85 * opacity,
      borderColor: border,
      borderOpacity: opacity,
      borderThickness: 1,
      inFront: true,
    });

  /** A metal bond or hydrogen bond: a dashed line from the metal or residue atom to the drug atom,
   * a hydrogen bond labelled at the residue end. */
  type Bond = { from: Point; to: Point; color: string; label: string | null };
  type Drawn = { line?: GLShape; label?: Label };

  /** Draws `bond` `amount` (0 to 1) of the way in, in place of what `drawn` holds of it: the line
   * reaches out from the drug to the residue, then the label fades in. */
  const drawBond = ({ from, to, color, label }: Bond, amount: number, drawn: Drawn) => {
    if (drawn.line) viewer.removeShape(drawn.line);
    if (drawn.label) viewer.removeLabel(drawn.label);
    drawn.line = undefined;
    drawn.label = undefined;
    if (amount <= 0) return;
    const reach = easeInOut(Math.min(1, amount / LINE_SHARE));
    const tip = {
      x: to.x + (from.x - to.x) * reach,
      y: to.y + (from.y - to.y) * reach,
      z: to.z + (from.z - to.z) * reach,
    };
    drawn.line = addDashedLine(tip, to, color);
    const labelIn = (amount - LINE_SHARE) / (1 - LINE_SHARE);
    if (label && labelIn > 0) drawn.label = addLabel(label, from, color, "topLeft", labelIn);
  };

  const showMetalLabel = (metal: MetalLabel) =>
    addLabel(metal.label, metal.position, colors.coordination, "center");

  const bonds: Bond[] = [
    ...coordinationBonds(complex).map((line) => ({
      from: line.metal,
      to: line.ligand,
      color: colors.coordination,
      label: null,
    })),
    ...hydrogenBonds(complex).map((bond) => ({
      from: bond.residue,
      to: bond.ligand,
      color: colors.hbond,
      label: bond.label,
    })),
  ];

  /** One function per bond that draws it `amount` (0 to 1) of the way in, replacing what it drew
   * before. Made again after the shapes and labels are cleared: 3Dmol reuses shape ids. */
  const bondDrawers = () =>
    bonds.map((bond) => {
      const drawn: Drawn = {};
      return (amount: number) => drawBond(bond, amount, drawn);
    });

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
    if (mode !== "molecule") bondDrawers().forEach((draw) => draw(1));
    viewer.render();
    turning.start();
  };

  /**
   * The drug builds itself up (`assemble`); outside Molecule mode it does so outside the pocket,
   * then the camera pulls back while the backbone grows and the metals and cofactors appear, the
   * drug docks with the camera on it while the pocket's residues grow in around it, nearest first,
   * and the metal bonds and hydrogen bonds reach out from the drug one by one. The path in is an
   * illustration; only the end pose is from the structure.
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
    const bondLines = bondDrawers();
    const duration = docks ? contacts + bondLines.length * CONTACT_MS : drug.duration;
    const fades = mode === "site";
    let traceStep = -1;
    let fadeStep = -1;
    let drawnBonds = 0;
    let inPose = false;
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
        const nextFade = Math.ceil(
          (Math.max(0, progress - FADE_FROM) / (1 - FADE_FROM)) * FADE_STEPS,
        );
        if (nextFade !== fadeStep) {
          fadeStep = nextFade;
          const shown = fadeStep / FADE_STEPS;
          showTrace(proteinSize, colors.traceOpacity * (fades ? 1 - shown : 1));
          showPocket(shown);
        }
      }
      if (docks && elapsed >= contacts) {
        if (!inPose) {
          inPose = true;
          placeLigand(bound);
          viewer.setView(viewAt(target, end));
          // A slow frame can end the docking before the last pocket step.
          if (fadeStep !== FADE_STEPS) {
            showTrace(fades ? 0 : proteinSize, colors.traceOpacity);
            showPocket();
          }
        }
        // The bonds come in one after the other, each over its own CONTACT_MS.
        for (let i = drawnBonds; i < bondLines.length; i++) {
          const amount = Math.min(1, (elapsed - contacts - i * CONTACT_MS) / CONTACT_MS);
          if (amount <= 0) break;
          bondLines[i](amount);
          if (amount === 1) drawnBonds = i + 1;
        }
      }
      viewer.render();
    };

    const finish = () => {
      playing.current = null;
      step(duration);
      if (docks) bondLines.slice(drawnBonds).forEach((draw) => draw(1));
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
