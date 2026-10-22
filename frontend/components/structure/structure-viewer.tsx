"use client";

import { useEffect, useImperativeHandle, useRef, useState, type Ref } from "react";

import { useShownTheme } from "@/lib/theme";
import { useMediaQuery } from "@/lib/use-media-query";

import {
  COLORS,
  createScene,
  type Camera,
  type Scene,
  type SceneData,
  type ViewMode,
} from "./scene";

export type StructureViewerHandle = { replay(): void; reset(): void };

// Browsers keep only about 16 live WebGL contexts per page and drop the oldest for a new one, so a
// view further off screen than this (two viewport heights) gives its context back. The margin is
// wide so that normal scrolling doesn't build views again all the time.
const NEARBY = "200% 0px";

/**
 * The 3D canvas. 3Dmol is bundled with the app, not fetched from a CDN, so the view works offline;
 * it is loaded only when a view first comes near the screen. The drug builds itself up, and in a
 * complex binds, the first time half of the view is on screen, and a view off screen stops turning. Far off screen the view
 * is closed, and it is built again with the same mode and camera when it comes back.
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
  const bindingPlayed = useRef(false);
  const savedCamera = useRef<{ data: SceneData; camera: Camera } | null>(null);
  const [near, setNear] = useState(false);
  const reportError = useRef(onError);
  const dark = useShownTheme() === "dark";
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
    const nearby = new IntersectionObserver(([entry]) => setNear(entry.isIntersecting), {
      rootMargin: NEARBY,
    });
    nearby.observe(container.current!);
    return () => nearby.disconnect();
  }, []);

  useEffect(() => {
    if (!near) return;
    const element = container.current!;
    const awaitsBinding = () => !reduceMotion && !bindingPlayed.current;
    // Hidden until the sequence starts, so the finished drug doesn't show and then fall apart.
    element.style.visibility = awaitsBinding() ? "hidden" : "";
    let cancelled = false;
    const visibility = new IntersectionObserver(
      ([entry]) => {
        scene.current?.setOnScreen(entry.isIntersecting);
        if (scene.current && awaitsBinding() && entry.intersectionRatio >= 0.5) {
          bindingPlayed.current = true;
          element.style.visibility = "";
          scene.current.replay();
        }
      },
      { threshold: [0, 0.5] },
    );
    const saved = savedCamera.current;
    import("3dmol")
      .then((lib) => {
        if (cancelled) return;
        scene.current = createScene(lib, element, data, {
          mode: shownMode.current,
          colors: dark ? COLORS.screenDark : COLORS.screen,
          reduceMotion,
          camera: saved?.data === data ? saved.camera : undefined,
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
      if (!scene.current) return;
      const camera = scene.current.camera();
      savedCamera.current = camera ? { data, camera } : null;
      scene.current.dispose();
      scene.current = null;
    };
  }, [data, dark, reduceMotion, near]);

  useEffect(() => {
    const previous = shownMode.current;
    shownMode.current = mode;
    if (previous === mode || !scene.current) return;
    // Switching before the binding played shows the new view at once.
    bindingPlayed.current = true;
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
