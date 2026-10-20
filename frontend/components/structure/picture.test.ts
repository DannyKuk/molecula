import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, getComplex, getStructure } from "@/lib/api";
import { SMALL_COMPLEX } from "@/lib/test-complexes";
import type { DrugComplex, StructureTarget } from "@/lib/tool-cards";

import { drawPicture } from "./picture";
import { createScene, type Scene } from "./scene";

// jsdom has no WebGL: the scene is a stand-in that hands back a picture.
vi.mock("3dmol", () => ({}));
vi.mock("./scene", () => ({ createScene: vi.fn() }));
vi.mock("@/lib/api", async (original) => ({
  ...(await original<typeof import("@/lib/api")>()),
  getComplex: vi.fn(),
  getStructure: vi.fn(),
}));

const PNG = "data:image/png;base64,iVBORw0KGgo=";

const imatinib: StructureTarget = {
  cid: 5291,
  name: "imatinib",
  complex: { pdb_id: "2HYY" } as DrugComplex,
};
const insulin: StructureTarget = { cid: 118984375, name: "insulin", complex: null };

function fakeScene(): Scene {
  const scene = { picture: vi.fn(() => PNG), dispose: vi.fn() } as unknown as Scene;
  vi.mocked(createScene).mockReturnValue(scene);
  return scene;
}

afterEach(() => {
  document.body.innerHTML = "";
});

describe("drawPicture", () => {
  it("draws a complex's binding site, light and still, and closes the view again", async () => {
    vi.mocked(getComplex).mockResolvedValue(SMALL_COMPLEX);
    const scene = fakeScene();

    const picture = await drawPicture(imatinib);

    expect(picture).toEqual({ status: "ready", png: PNG, complex: SMALL_COMPLEX });
    const [, host, data, options] = vi.mocked(createScene).mock.calls[0];
    expect(data).toEqual({ kind: "complex", complex: SMALL_COMPLEX });
    expect(options).toEqual({ mode: "site", dark: false, reduceMotion: true });
    expect(host.style.width).toBe("720px");
    expect(scene.dispose).toHaveBeenCalledOnce();
    expect(document.body.children).toHaveLength(0);
  });

  it("draws a drug without a complex as the molecule alone", async () => {
    vi.mocked(getStructure).mockResolvedValue("SDF");
    fakeScene();

    const picture = await drawPicture(insulin);

    expect(picture).toEqual({ status: "ready", png: PNG, complex: null });
    const [, , data, options] = vi.mocked(createScene).mock.calls[0];
    expect(data).toEqual({ kind: "molecule", sdf: "SDF" });
    expect(options.mode).toBe("molecule");
  });

  it("has no picture for a drug without a 3D model", async () => {
    vi.mocked(getStructure).mockRejectedValue(new ApiError("/drugs/118984375/structure", 404));

    expect(await drawPicture(insulin)).toEqual({ status: "missing" });
    expect(createScene).not.toHaveBeenCalled();
  });

  it("fails when the structure can't be loaded", async () => {
    vi.mocked(getComplex).mockRejectedValue(new ApiError("/drugs/5291/complex", 503));

    await expect(drawPicture(imatinib)).rejects.toThrow(ApiError);
  });
});
