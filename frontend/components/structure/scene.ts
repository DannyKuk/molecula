import type { GLViewer } from "3dmol";

import type { Complex } from "@/lib/api";
import {
  approachDirection,
  centroid,
  dockingPose,
  easeInOut,
  hydrogenBonds,
  ligandAtoms,
  pocketSelection,
  proteinAtoms,
  type Point,
} from "@/lib/complex-scene";

type ThreeDmol = typeof import("3dmol");

/** What the 3D view shows: the drug alone, the drug in its pocket, or that plus the backbone. */
export type ViewMode = "molecule" | "site" | "protein";

export type SceneData = { kind: "complex"; complex: Complex } | { kind: "molecule"; sdf: string };

export type SceneOptions = { mode: ViewMode; dark: boolean; reduceMotion: boolean };

export type Scene = {
  /** Switches the view; `animate` plays the binding when the pocket comes into view. */
  setMode(mode: ViewMode, animate: boolean): void;
  /** Plays the binding again, or for a molecule just recenters it. */
  replay(): void;
  reset(): void;
  /** A view scrolled off screen stops turning, so the views further up the chat cost nothing. */
  setOnScreen(onScreen: boolean): void;
  resize(): void;
  dispose(): void;
};

const COLORS = {
  dark: { trace: "#a1a1aa", label: "#fafafa", labelBackground: "#18181b", hbond: "#fbbf24" },
  light: { trace: "#71717a", label: "#18181b", labelBackground: "#ffffff", hbond: "#d97706" },
};

const ZOOM: Record<ViewMode, number> = { molecule: 0.9, site: 0.75, protein: 0.5 };

const DOCK_MS = 2600;
// The camera holds the Molecule zoom while the drug travels and only pulls back once it is close.
const ZOOM_OUT_FROM = 0.55;
const SPIN_SPEED = 0.25;
// Wider than any stored complex: `zoomTo` on the drug would otherwise clip the protein around it.
const SLAB = 500;

/** The slow turn: on once the view is settled, held while it is off screen, and stopped for good
 * when the user grabs the view, until Reset or Replay. */
type Turning = { start(): void; stop(): void; release(): void; grabbed(): boolean };

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
  const viewer = lib.createViewer(box, { backgroundAlpha: 0, antialias: true });
  let wanted = false;
  let onScreen = true;
  let grabbed = false;
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
    grabbed: () => grabbed,
  };
  const grab = () => {
    grabbed = true;
    apply();
  };
  box.addEventListener("pointerdown", grab);
  const common = {
    setOnScreen: (visible: boolean) => {
      onScreen = visible;
      apply();
    },
    resize: () => {
      viewer.resize();
      viewer.render();
    },
    dispose: () => {
      box.removeEventListener("pointerdown", grab);
      viewer.spin(false);
      viewer.clear();
      releaseContext(box);
      box.remove();
    },
  };

  if (data.kind === "molecule") {
    viewer.addModel(data.sdf, "sdf");
    viewer.setStyle({}, { stick: { radius: 0.15 }, sphere: { scale: 0.25 } });
    const reset = () => {
      turning.release();
      viewer.zoomTo();
      viewer.setSlab(-SLAB, SLAB);
      viewer.render();
      turning.start();
    };
    reset();
    return { ...common, setMode: () => {}, replay: reset, reset };
  }

  return complexScene(viewer, data.complex, options, turning, common);
}

function complexScene(
  viewer: GLViewer,
  complex: Complex,
  options: SceneOptions,
  turning: Turning,
  common: Pick<Scene, "setOnScreen" | "resize" | "dispose">,
): Scene {
  const colors = options.dark ? COLORS.dark : COLORS.light;
  const protein = viewer.addModel();
  protein.addAtoms(proteinAtoms(complex));
  protein.assignBonds();
  const ligand = viewer.addModel();
  ligand.addAtoms(ligandAtoms(complex.ligand));
  const atoms = ligand.selectedAtoms({});
  const bound = atoms.map(({ x, y, z }) => ({ x: x!, y: y!, z: z! }));
  const center = centroid(bound);
  const approach = approachDirection(complex);
  const pocket = pocketSelection(complex);
  const bonds = hydrogenBonds(complex);
  let mode = options.mode;
  let frame = 0;
  let ligandStyle = {};

  const placeLigand = (positions: Point[]) => {
    atoms.forEach((atom, i) => Object.assign(atom, positions[i]));
    // Restyling makes 3Dmol rebuild the drug's geometry at the new positions.
    ligand.setStyle({}, ligandStyle);
  };

  const showContacts = () => {
    for (const bond of bonds) {
      viewer.addCylinder({
        start: bond.residue,
        end: bond.ligand,
        radius: 0.09,
        dashed: true,
        dashLength: 0.25,
        gapLength: 0.15,
        color: colors.hbond,
        fromCap: 1,
        toCap: 1,
      });
      viewer.addLabel(bond.label, {
        position: bond.residue,
        fontSize: 12,
        fontColor: colors.label,
        backgroundColor: colors.labelBackground,
        backgroundOpacity: 0.85,
        borderColor: colors.hbond,
        borderThickness: 1,
        inFront: true,
      });
    }
  };

  // 3Dmol's view is [-center x, -center y, -center z, camera distance, rotation quaternion x y z w];
  // keeping the rotation lets the camera follow the drug without turning.
  const viewAt = (target: Point, distance: number) => {
    const [, , , , ...rotation] = viewer.getView();
    return [-target.x, -target.y, -target.z, distance, ...rotation];
  };

  const distanceFor = (target: ViewMode) => {
    const current = viewer.getView();
    viewer.zoomTo({ model: ligand });
    viewer.zoom(ZOOM[target]);
    const distance = viewer.getView()[3];
    viewer.setView(current);
    viewer.setSlab(-SLAB, SLAB);
    return distance;
  };

  const dock = (from: number, to: number) => {
    const start = performance.now();
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / DOCK_MS);
      const positions = dockingPose(bound, approach, progress);
      placeLigand(positions);
      // Once the user grabs the view, the camera is theirs.
      if (!turning.grabbed()) {
        const pullBack = easeInOut(Math.max(0, (progress - ZOOM_OUT_FROM) / (1 - ZOOM_OUT_FROM)));
        viewer.setView(viewAt(centroid(positions), from + (to - from) * pullBack));
      }
      viewer.render();
      if (progress < 1) {
        frame = requestAnimationFrame(tick);
      } else {
        showContacts();
        viewer.render();
        turning.start();
      }
    };
    frame = requestAnimationFrame(tick);
  };

  let framed = false;
  const setMode = (next: ViewMode, animate: boolean) => {
    mode = next;
    cancelAnimationFrame(frame);
    turning.stop();
    viewer.removeAllShapes();
    viewer.removeAllLabels();
    const carbons = next === "molecule" ? "default" : "greenCarbon";
    ligandStyle = {
      stick: { radius: 0.2, colorscheme: carbons },
      sphere: { scale: 0.25, colorscheme: carbons },
    };
    protein.setStyle(
      {},
      next === "protein"
        ? { cartoon: { style: "trace", color: colors.trace, thickness: 0.3, opacity: 0.35 } }
        : {},
    );
    if (next !== "molecule") protein.setStyle(pocket, { stick: { radius: 0.12 } }, true);
    placeLigand(bound);
    if (!framed) {
      viewer.zoomTo({ model: ligand });
      framed = true;
    }
    const to = distanceFor(next);
    if (next === "molecule" || !animate || options.reduceMotion) {
      viewer.setView(viewAt(center, to));
      if (next !== "molecule") showContacts();
      viewer.render();
      turning.start();
    } else {
      dock(distanceFor("molecule"), to);
    }
  };

  setMode(mode, false);
  return {
    ...common,
    setMode,
    replay: () => {
      turning.release();
      setMode(mode, true);
    },
    reset: () => {
      turning.release();
      setMode(mode, false);
    },
    dispose: () => {
      cancelAnimationFrame(frame);
      common.dispose();
    },
  };
}

/** Browsers allow only a few live WebGL contexts per page, so a closed view gives its back. */
function releaseContext(element: HTMLElement) {
  const canvas = element.querySelector("canvas");
  const gl = canvas?.getContext("webgl2") ?? canvas?.getContext("webgl");
  gl?.getExtension("WEBGL_lose_context")?.loseContext();
  canvas?.remove();
}
