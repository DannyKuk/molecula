import { act, render, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import { SMALL_COMPLEX } from "@/lib/test-complexes";

import { createScene, type Scene, type SceneData } from "./scene";
import { StructureViewer } from "./structure-viewer";

vi.mock("3dmol", () => ({}));
vi.mock("./scene", () => ({ createScene: vi.fn() }));

let scene: { [K in keyof Scene]: Mock<() => void> };
let reportVisibility: (entry: Partial<IntersectionObserverEntry>) => void;

beforeEach(() => {
  scene = {
    setMode: vi.fn<() => void>(),
    replay: vi.fn<() => void>(),
    reset: vi.fn<() => void>(),
    setOnScreen: vi.fn<() => void>(),
    resize: vi.fn<() => void>(),
    dispose: vi.fn<() => void>(),
  };
  vi.mocked(createScene).mockReturnValue(scene);
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      constructor(callback: (entries: Partial<IntersectionObserverEntry>[]) => void) {
        reportVisibility = (entry) => callback([entry]);
      }
      observe() {}
      disconnect() {}
    },
  );
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
    },
  );
});

// Defined for the whole file, not per test: effects still running after a test ends read it.
beforeAll(() => {
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: () => ({ matches: false, addEventListener: () => {}, removeEventListener: () => {} }),
  });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

const complex: SceneData = { kind: "complex", complex: SMALL_COMPLEX };
const molecule: SceneData = { kind: "molecule", sdf: "1983\n$$$$\n" };

function renderViewer(data: SceneData, mode: "molecule" | "site" | "protein", onError = vi.fn()) {
  const view = render(<StructureViewer data={data} mode={mode} label="View" onError={onError} />);
  return { ...view, element: view.container.firstChild as HTMLElement };
}

describe("StructureViewer", () => {
  it("keeps a complex hidden until half of it is on screen, then plays the binding", async () => {
    const { element } = renderViewer(complex, "site");
    await waitFor(() => expect(createScene).toHaveBeenCalled());
    expect(element.style.visibility).toBe("hidden");

    act(() => reportVisibility({ isIntersecting: true, intersectionRatio: 0.2 }));
    expect(scene.replay).not.toHaveBeenCalled();

    act(() => reportVisibility({ isIntersecting: true, intersectionRatio: 0.6 }));
    expect(element.style.visibility).toBe("");
    expect(scene.replay).toHaveBeenCalledOnce();
  });

  it("shows a molecule at once and stops it turning while it is off screen", async () => {
    const { element } = renderViewer(molecule, "molecule");
    await waitFor(() => expect(createScene).toHaveBeenCalled());
    expect(element.style.visibility).toBe("");

    act(() => reportVisibility({ isIntersecting: false, intersectionRatio: 0 }));

    expect(scene.setOnScreen).toHaveBeenCalledWith(false);
    expect(scene.replay).not.toHaveBeenCalled();
  });

  it("plays the binding when the view leaves Molecule, and shows it at once", async () => {
    const { element, rerender } = renderViewer(complex, "molecule");
    await waitFor(() => expect(createScene).toHaveBeenCalled());

    rerender(<StructureViewer data={complex} mode="site" label="View" onError={vi.fn()} />);
    expect(scene.setMode).toHaveBeenLastCalledWith("site", true);

    rerender(<StructureViewer data={complex} mode="protein" label="View" onError={vi.fn()} />);
    expect(scene.setMode).toHaveBeenLastCalledWith("protein", false);
    expect(element.style.visibility).toBe("");
  });

  it("gives the view back when it goes away", async () => {
    const { unmount } = renderViewer(molecule, "molecule");
    await waitFor(() => expect(createScene).toHaveBeenCalled());

    unmount();

    expect(scene.dispose).toHaveBeenCalledOnce();
  });

  it("reports a view that can't be drawn", async () => {
    vi.mocked(createScene).mockImplementation(() => {
      throw new Error("WebGL is not available");
    });
    const onError = vi.fn();

    renderViewer(molecule, "molecule", onError);

    await waitFor(() => expect(onError).toHaveBeenCalledOnce());
  });
});
