"use client";

import { useEffect, useImperativeHandle, useRef, type Ref } from "react";

import { useMediaQuery } from "@/lib/use-media-query";

import { createScene, type Scene, type SceneData, type ViewMode } from "./scene";

export type StructureViewerHandle = { replay(): void; reset(): void };

/**
 * The 3D canvas. 3Dmol is bundled with the app, not fetched from a CDN, so the view works offline;
 * it is loaded only when a view first appears. A complex plays its binding the first time half of
 * the view is on screen, and a view off screen stops turning.
 */
export function StructureViewer({
  data,
  mode,
  label,
  onError,
  className,
  ref,
}: {
  data: SceneData;
  mode: ViewMode;
  label: string;
  /** Called when the view can't be drawn, e.g. without WebGL. */
  onError: () => void;
  className?: string;
  ref?: Ref<StructureViewerHandle>;
}) {
  const container = useRef<HTMLDivElement>(null);
  const scene = useRef<Scene | null>(null);
  const shownMode = useRef(mode);
  const reportError = useRef(onError);
  const dark = useMediaQuery("(prefers-color-scheme: dark)");
  const reduceMotion = useMediaQuery("(prefers-reduced-motion: reduce)");

  useImperativeHandle(
    ref,
    () => ({ replay: () => scene.current?.replay(), reset: () => scene.current?.reset() }),
    [],
  );

  useEffect(() => {
    reportError.current = onError;
  }, [onError]);

  useEffect(() => {
    const element = container.current!;
    let waitingForBinding =
      data.kind === "complex" && shownMode.current !== "molecule" && !reduceMotion;
    // Hidden until the binding starts, so the drug doesn't show in its pocket and then jump out.
    element.style.visibility = waitingForBinding ? "hidden" : "";
    let cancelled = false;
    const reveal = () => {
      waitingForBinding = false;
      element.style.visibility = "";
    };
    const visibility = new IntersectionObserver(
      ([entry]) => {
        scene.current?.setOnScreen(entry.isIntersecting);
        if (waitingForBinding && scene.current && entry.intersectionRatio >= 0.5) {
          reveal();
          scene.current.replay();
        }
      },
      { threshold: [0, 0.5] },
    );
    import("3dmol")
      .then((lib) => {
        if (cancelled) return;
        scene.current = createScene(lib, element, data, {
          mode: shownMode.current,
          dark,
          reduceMotion,
        });
        visibility.observe(element);
      })
      .catch(() => {
        if (!cancelled) reportError.current();
      });
    const resizes = new ResizeObserver(() => scene.current?.resize());
    resizes.observe(element);
    return () => {
      cancelled = true;
      visibility.disconnect();
      resizes.disconnect();
      scene.current?.dispose();
      scene.current = null;
    };
  }, [data, dark, reduceMotion]);

  useEffect(() => {
    const previous = shownMode.current;
    shownMode.current = mode;
    if (previous === mode || !scene.current) return;
    // Switching before the binding played shows the new view at once.
    container.current!.style.visibility = "";
    scene.current.setMode(mode, previous === "molecule");
  }, [mode]);

  return (
    <div
      ref={container}
      role="img"
      aria-label={label}
      className={`relative overflow-hidden ${className ?? ""}`}
    />
  );
}
