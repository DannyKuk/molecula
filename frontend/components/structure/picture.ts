import { ApiError, getComplex, getStructure } from "@/lib/api";
import type { Picture } from "@/lib/printed-pictures";
import type { StructureTarget } from "@/lib/tool-cards";

import { COLORS, createScene, type SceneData } from "./scene";

// The hidden view's size in CSS pixels. 3Dmol draws an antialiased view at twice that at least, so
// the picture is 1440 × 960 pixels or more, sharp at the width it prints.
const WIDTH = 720;
const HEIGHT = 480;

/**
 * Draws a drug's 3D view off screen as the evidence panel first shows it (the binding site of a
 * complex, else the molecule), at its starting angle and in the light colours, and returns it as
 * a PNG. The view is closed again at once, so it holds a WebGL context only while it draws.
 */
export async function drawPicture(target: StructureTarget): Promise<Picture> {
  let data: SceneData;
  try {
    data = target.complex
      ? { kind: "complex", complex: await getComplex(target.cid) }
      : { kind: "molecule", sdf: await getStructure(target.cid) };
  } catch (error) {
    if (!target.complex && error instanceof ApiError && error.status === 404) {
      return { status: "missing" };
    }
    throw error;
  }
  const lib = await import("3dmol");
  // Off the page rather than `display: none`, which would give the canvas no size to draw at.
  const host = document.createElement("div");
  host.setAttribute("aria-hidden", "true");
  host.style.cssText = `position: fixed; top: 0; left: -10000px; width: ${WIDTH}px; height: ${HEIGHT}px;`;
  document.body.append(host);
  try {
    const scene = createScene(lib, host, data, {
      mode: data.kind === "complex" ? "site" : "molecule",
      colors: COLORS.paper,
      reduceMotion: true,
    });
    const png = scene.picture();
    scene.dispose();
    return { status: "ready", png, complex: data.kind === "complex" ? data.complex : null };
  } finally {
    host.remove();
  }
}
