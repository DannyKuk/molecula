import type { Complex } from "./api";
import type { Turn } from "./chat-turn";
import { structuresOf, type StructureTarget } from "./tool-cards";

/** A drug's 3D view as a still picture for paper; `missing` is a drug without a 3D model. */
export type Picture =
  | { status: "ready"; png: string; complex: Complex | null; elements: string[] }
  | { status: "missing" }
  | { status: "failed" };

/** The pictures drawn so far, by the drug's CID. */
export type Pictures = ReadonlyMap<number, Picture>;

export type DrawPicture = (target: StructureTarget) => Promise<Picture>;

// A view that hasn't drawn by then (a lost WebGL context, a stalled request) prints as failed
// instead of holding back the print dialog.
export const DRAW_TIMEOUT_MS = 20_000;

/** The drugs the conversation shows in 3D that have no picture yet, each once. One that failed is
 * tried again. */
export function picturesToDraw(turns: Turn[], pictures: Pictures): StructureTarget[] {
  const targets = new Map<number, StructureTarget>();
  for (const turn of turns) {
    for (const target of structuresOf(turn.steps)) {
      const drawn = pictures.get(target.cid);
      if (drawn?.status !== "failed" && drawn !== undefined) continue;
      if (!targets.has(target.cid)) targets.set(target.cid, target);
    }
  }
  return [...targets.values()];
}

/** Draws the pictures one after the other, because browsers keep only a few live WebGL contexts
 * per page. A picture that fails or takes too long comes back as failed. */
export async function drawPictures(
  targets: StructureTarget[],
  draw: DrawPicture,
): Promise<Map<number, Picture>> {
  const drawn = new Map<number, Picture>();
  for (const target of targets) {
    drawn.set(target.cid, await withTimeout(draw(target)).catch(() => FAILED));
  }
  return drawn;
}

const FAILED: Picture = { status: "failed" };

function withTimeout(picture: Promise<Picture>): Promise<Picture> {
  let timer: ReturnType<typeof setTimeout> | undefined;
  const late = new Promise<Picture>((resolve) => {
    timer = setTimeout(() => resolve(FAILED), DRAW_TIMEOUT_MS);
  });
  return Promise.race([picture, late]).finally(() => clearTimeout(timer));
}
