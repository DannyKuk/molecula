import { readFile } from "node:fs/promises";
import { join } from "node:path";

// The picture of the preview card a shared link shows (#461), drawn once from the landing page's
// 3D view (docs/design/app.md). It is served from here rather than as `opengraph-image.png`
// because Turbopack ignores the `.alt.txt` file beside a static picture.
export const alt =
  'Imatinib, a leukemia drug, bound in the pocket of its target ABL1 in Molecula\'s 3D view, beside the words "Ask how a medicine works. Watch it bind."';
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function PreviewCard() {
  return new Response(await readPicture(), { headers: { "Content-Type": contentType } });
}

// Cached, so the build prerenders the route instead of the server reading the file per request.
async function readPicture(): Promise<Uint8Array<ArrayBuffer>> {
  "use cache";
  return new Uint8Array(await readFile(join(process.cwd(), "app", "preview-card.png")));
}
