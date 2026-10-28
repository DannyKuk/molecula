import { act, render, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi, type Mock } from "vitest";

import { SMALL_COMPLEX } from "@/lib/test-complexes";

import { createScene, type Camera, type Scene, type SceneData } from "./scene";
import { StructureViewer } from "./structure-viewer";

vi.mock("3dmol", () => ({}));
vi.mock("./scene", async (original) => ({
  ...(await original<typeof import("./scene")>()),
  createScene: vi.fn(),
}));

type FakeScene = { [K in keyof Scene]: Mock<Scene[K]> };
type Report = (entry: Partial<IntersectionObserverEntry>) => void;

let scenes: FakeScene[];
let reportVisibility: Report;
let reportNearby: Report;

function fakeScene(): FakeScene {
  return {
    setMode: vi.fn<Scene["setMode"]>(),
    replay: vi.fn<Scene["replay"]>(),
    reset: vi.fn<Scene["reset"]>(),
    setOnScreen: vi.fn<Scene["setOnScreen"]>(),
    camera: vi.fn<Scene["camera"]>(() => null),
    resize: vi.fn<Scene["resize"]>(),
    picture: vi.fn<Scene["picture"]>(() => ""),
    dispose: vi.fn<Scene["dispose"]>(),
  };
}

beforeEach(() => {
  scenes = [];
  vi.mocked(createScene).mockImplementation(() => {
    const scene = fakeScene();
    scenes.push(scene);
    return scene;
  });
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      constructor(
        callback: (entries: Partial<IntersectionObserverEntry>[]) => void,
        options?: IntersectionObserverInit,
      ) {
        const report: Report = (entry) => callback([entry]);
        if (options?.rootMargin) reportNearby = report;
        else reportVisibility = report;
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

/** Renders the viewer near the screen, where it builds its scene. */
function renderViewer(data: SceneData, mode: "molecule" | "site" | "protein", onError = vi.fn()) {
  const view = render(<StructureViewer data={data} mode={mode} label="View" onError={onError} />);
  act(() => reportNearby({ isIntersecting: true }));
  return { ...view, element: view.container.firstChild as HTMLElement };
}

function moveFarAway() {
  act(() => reportNearby({ isIntersecting: false }));
}

async function comeBack() {
  const built = scenes.length;
  act(() => reportNearby({ isIntersecting: true }));
  await waitFor(() => expect(scenes).toHaveLength(built + 1));
}

describe("StructureViewer", () => {
  it("keeps a complex hidden until half of it is on screen, then plays the binding", async () => {
    const { element } = renderViewer(complex, "site");
    await waitFor(() => expect(createScene).toHaveBeenCalled());
    expect(element.style.visibility).toBe("hidden");

    act(() => reportVisibility({ isIntersecting: true, intersectionRatio: 0.2 }));
    expect(scenes[0].replay).not.toHaveBeenCalled();

    act(() => reportVisibility({ isIntersecting: true, intersectionRatio: 0.6 }));
    expect(element.style.visibility).toBe("");
    expect(scenes[0].replay).toHaveBeenCalledOnce();
  });

  it("builds a molecule up the first time half of it is on screen, and stops it turning off screen", async () => {
    const { element } = renderViewer(molecule, "molecule");
    await waitFor(() => expect(createScene).toHaveBeenCalled());
    expect(element.style.visibility).toBe("hidden");

    act(() => reportVisibility({ isIntersecting: true, intersectionRatio: 0.5 }));
    expect(scenes[0].replay).toHaveBeenCalledOnce();
    expect(element.style.visibility).toBe("");

    act(() => reportVisibility({ isIntersecting: false, intersectionRatio: 0 }));
    expect(scenes[0].setOnScreen).toHaveBeenLastCalledWith(false);
    expect(scenes[0].replay).toHaveBeenCalledOnce();
  });

  it("plays the binding when the view leaves Molecule, and shows it at once", async () => {
    const { element, rerender } = renderViewer(complex, "molecule");
    await waitFor(() => expect(createScene).toHaveBeenCalled());

    rerender(<StructureViewer data={complex} mode="site" label="View" onError={vi.fn()} />);
    expect(scenes[0].setMode).toHaveBeenLastCalledWith("site", true);

    rerender(<StructureViewer data={complex} mode="protein" label="View" onError={vi.fn()} />);
    expect(scenes[0].setMode).toHaveBeenLastCalledWith("protein", false);
    expect(element.style.visibility).toBe("");
  });

  it("gives the view back when it goes away", async () => {
    const { unmount } = renderViewer(molecule, "molecule");
    await waitFor(() => expect(createScene).toHaveBeenCalled());

    unmount();

    expect(scenes[0].dispose).toHaveBeenCalledOnce();
  });

  it("reports a view that can't be drawn", async () => {
    vi.mocked(createScene).mockImplementation(() => {
      throw new Error("WebGL is not available");
    });
    const onError = vi.fn();

    renderViewer(molecule, "molecule", onError);

    await waitFor(() => expect(onError).toHaveBeenCalledOnce());
  });

  it("builds nothing for a view that never comes near the screen", async () => {
    render(<StructureViewer data={molecule} mode="molecule" label="View" onError={vi.fn()} />);

    await act(async () => {});

    expect(createScene).not.toHaveBeenCalled();
  });

  it("gives back a view far off screen and builds it again in its mode, without replaying", async () => {
    const { element, rerender } = renderViewer(complex, "site");
    await waitFor(() => expect(createScene).toHaveBeenCalledOnce());
    act(() => reportVisibility({ isIntersecting: true, intersectionRatio: 0.6 }));
    rerender(<StructureViewer data={complex} mode="protein" label="View" onError={vi.fn()} />);

    moveFarAway();

    expect(scenes[0].dispose).toHaveBeenCalledOnce();
    expect(createScene).toHaveBeenCalledOnce();

    await comeBack();

    expect(vi.mocked(createScene).mock.calls[1][3]).toMatchObject({ mode: "protein" });
    expect(element.style.visibility).toBe("");
    act(() => reportVisibility({ isIntersecting: true, intersectionRatio: 0.6 }));
    expect(scenes[1].replay).not.toHaveBeenCalled();
  });

  it("plays the binding once when a view given back before it played comes back", async () => {
    const { element } = renderViewer(complex, "site");
    await waitFor(() => expect(createScene).toHaveBeenCalledOnce());

    moveFarAway();
    await comeBack();

    expect(element.style.visibility).toBe("hidden");
    act(() => reportVisibility({ isIntersecting: true, intersectionRatio: 0.6 }));
    expect(element.style.visibility).toBe("");
    expect(scenes[0].replay).not.toHaveBeenCalled();
    expect(scenes[1].replay).toHaveBeenCalledOnce();
  });

  it("builds a view again where its camera was", async () => {
    renderViewer(molecule, "molecule");
    await waitFor(() => expect(createScene).toHaveBeenCalledOnce());
    const camera: Camera = { view: [1, 2, 3, 40, 0, 0, 0, 1], grabbed: true };
    scenes[0].camera.mockReturnValue(camera);

    moveFarAway();
    await comeBack();

    expect(vi.mocked(createScene).mock.calls[1][3].camera).toEqual(camera);
  });

  it("keeps the camera when a view goes away again before it was built", async () => {
    renderViewer(molecule, "molecule");
    await waitFor(() => expect(createScene).toHaveBeenCalledOnce());
    const camera: Camera = { view: [1, 2, 3, 40, 0, 0, 0, 1], grabbed: false };
    scenes[0].camera.mockReturnValue(camera);
    moveFarAway();

    act(() => reportNearby({ isIntersecting: true }));
    moveFarAway();
    await comeBack();

    expect(vi.mocked(createScene).mock.calls[1][3].camera).toEqual(camera);
  });

  it("builds a view again in its default framing when it was given back mid-binding", async () => {
    renderViewer(complex, "site");
    await waitFor(() => expect(createScene).toHaveBeenCalledOnce());
    scenes[0].camera.mockReturnValue(null);

    moveFarAway();
    await comeBack();

    expect(vi.mocked(createScene).mock.calls[1][3].camera).toBeUndefined();
  });

  it("gives the view back only once when it goes away while far off screen", async () => {
    const { unmount } = renderViewer(molecule, "molecule");
    await waitFor(() => expect(createScene).toHaveBeenCalledOnce());

    moveFarAway();
    unmount();

    expect(scenes[0].dispose).toHaveBeenCalledOnce();
  });

  it("reports a view that can't be drawn again when it comes back", async () => {
    const onError = vi.fn();
    renderViewer(molecule, "molecule", onError);
    await waitFor(() => expect(createScene).toHaveBeenCalledOnce());
    vi.mocked(createScene).mockImplementation(() => {
      throw new Error("WebGL is not available");
    });

    moveFarAway();
    act(() => reportNearby({ isIntersecting: true }));

    await waitFor(() => expect(onError).toHaveBeenCalledOnce());
  });

  it("leaves the wheel and a finger to the page with scrollsPage, and a mouse to the view", () => {
    const view = render(
      <StructureViewer data={complex} mode="site" label="View" onError={vi.fn()} scrollsPage />,
    );
    const canvas = document.createElement("canvas");
    (view.container.firstChild as HTMLElement).append(canvas);
    const reached = vi.fn();
    for (const type of ["wheel", "touchmove", "pointerdown"])
      canvas.addEventListener(type, reached);

    const wheel = new Event("wheel", { bubbles: true, cancelable: true });
    canvas.dispatchEvent(wheel);
    canvas.dispatchEvent(new Event("touchmove", { bubbles: true }));
    canvas.dispatchEvent(pointerDown("touch"));
    expect(reached).not.toHaveBeenCalled();
    expect(wheel.defaultPrevented).toBe(false);

    canvas.dispatchEvent(pointerDown("mouse"));
    expect(reached).toHaveBeenCalledOnce();
  });
});

function pointerDown(pointerType: string): Event {
  return Object.assign(new Event("pointerdown", { bubbles: true }), { pointerType });
}
