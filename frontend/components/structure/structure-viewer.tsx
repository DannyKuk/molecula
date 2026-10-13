"use client";

import { useEffect, useImperativeHandle, useRef, type Ref } from "react";

import { useMediaQuery } from "@/lib/use-media-query";

import { createScene, type Scene, type SceneData, type ViewMode } from "./scene";

export type StructureViewerHandle = { replay(): void; reset(): void };

/**
 * The 3D canvas. 3Dmol is bundled with the app, not fetched from a CDN, so the view works offline;
 * it is loaded only when a view first appears. A complex plays its binding the first time half of
 * the view is on screen.
 */
export function StructureViewer({
  data,
  mode,
  label,
  className,
  ref,
}: {
  data: SceneData;
  mode: ViewMode;
  label: string;
  className?: string;
  ref?: Ref<StructureViewerHandle>;
}) {
  const container = useRef<HTMLDivElement>(null);
  const scene = useRef<Scene | null>(null);
  const shownMode = useRef(mode);
  const dark = useMediaQuery("(prefers-color-scheme: dark)");
  const reduceMotion = useMediaQuery("(prefers-reduced-motion: reduce)");

  useImperativeHandle(
    ref,
    () => ({ replay: () => scene.current?.replay(), reset: () => scene.current?.reset() }),
    [],
  );

  useEffect(() => {
    const element = container.current!;
    const playsBinding =
      data.kind === "complex" && shownMode.current !== "molecule" && !reduceMotion;
    // Hidden until the binding starts, so the drug doesn't show in its pocket and then jump out.
    element.style.visibility = playsBinding ? "hidden" : "";
    let cancelled = false;
    let stopWatching = () => {};
    import("3dmol").then((lib) => {
      if (cancelled) return;
      scene.current = createScene(lib, element, data, {
        mode: shownMode.current,
        dark,
        reduceMotion,
      });
      if (playsBinding) {
        stopWatching = onceHalfVisible(element, () => {
          element.style.visibility = "";
          scene.current?.replay();
        });
      }
    });
    const resizes = new ResizeObserver(() => scene.current?.resize());
    resizes.observe(element);
    return () => {
      cancelled = true;
      stopWatching();
      resizes.disconnect();
      scene.current?.dispose();
      scene.current = null;
    };
  }, [data, dark, reduceMotion]);

  useEffect(() => {
    const previous = shownMode.current;
    shownMode.current = mode;
    if (previous !== mode) scene.current?.setMode(mode, previous === "molecule");
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

function onceHalfVisible(element: HTMLElement, callback: () => void): () => void {
  const observer = new IntersectionObserver(
    ([entry]) => {
      if (!entry.isIntersecting) return;
      observer.disconnect();
      callback();
    },
    { threshold: 0.5 },
  );
  observer.observe(element);
  return () => observer.disconnect();
}
