"use client";

import { cn } from "cn";
import { Play } from "lucide-react";
import { type ReactNode, type RefObject, useEffect, useRef, useState } from "react";

import type { Complex } from "@/lib/api";
import { useMessages } from "@/lib/messages";
import { useMediaQuery } from "@/lib/use-media-query";

import { readout } from "../structure/readout";
import type { SceneData, ViewMode } from "../structure/scene";
import { StructureViewer, type StructureViewerHandle } from "../structure/structure-viewer";
import IMATINIB_2HYY from "./imatinib-2hyy.json";

// Bundled with the page, so a visitor who isn't signed in sees the view without a backend request.
// JSON imports type arrays loosely, so the coordinates need the cast to `Complex`'s tuples.
const IMATINIB: SceneData = {
  kind: "complex",
  complex: {
    ...IMATINIB_2HYY,
    source_url: "https://www.rcsb.org/structure/2HYY",
  } as unknown as Complex,
};

const MODES: ViewMode[] = ["molecule", "site", "protein"];

// The view is drawn this much larger than its area and shown scaled down, so scrolling can zoom it
// in up to its full size without blurring the canvas.
const SMALLEST = 0.72;
const FULL_SIZE = `${100 / SMALLEST}%`;

/** The landing page's top: the app's dark 3D screen across the page, with imatinib binding in
 * ABL1 behind the headline. The page keeps the wheel; scrolling down zooms the view in. */
export function LandingScreen({ nav, children }: { nav: ReactNode; children: ReactNode }) {
  const t = useMessages();
  const s = t.landing.screen;
  const [mode, setMode] = useState<ViewMode>("site");
  const [drawFailed, setDrawFailed] = useState(false);
  const viewer = useRef<StructureViewerHandle>(null);
  const reduceMotion = useMediaQuery("(prefers-reduced-motion: reduce)");
  const canDrag = useMediaQuery("(pointer: fine)");
  const zoomed = useScrollZoom(reduceMotion);

  return (
    <section className="relative flex min-h-[620px] flex-col overflow-hidden bg-screen text-screen-ink md:h-[min(88svh,860px)]">
      {!drawFailed && (
        <div className="absolute inset-x-0 top-0 bottom-[38%] md:inset-y-0 md:right-0 md:left-[36%]">
          <div
            ref={zoomed}
            style={{ width: FULL_SIZE, height: FULL_SIZE, transform: `scale(${SMALLEST})` }}
            className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2"
          >
            <StructureViewer
              ref={viewer}
              data={IMATINIB}
              mode={mode}
              label={s.label}
              onError={() => setDrawFailed(true)}
              scrollsPage
              className="size-full"
            />
          </div>
        </div>
      )}
      {/* The fades keep the text readable where the protein reaches under it. */}
      <div className="pointer-events-none absolute inset-x-0 top-0 h-40 bg-linear-to-b from-screen to-transparent" />
      <div className="pointer-events-none absolute inset-x-0 bottom-0 h-[62%] bg-linear-to-t from-screen from-35% to-transparent md:h-1/2 md:from-10%" />
      <div
        aria-hidden
        className="viewfinder pointer-events-none absolute inset-x-3 top-[72px] bottom-3"
      />

      <div className="relative z-10 px-4 md:px-10">{nav}</div>
      <div className="pointer-events-none relative z-10 flex items-start justify-between gap-4 px-6 pt-4 md:px-12">
        <p className="text-[15px] leading-snug font-semibold">
          {s.title}
          <span className="block font-mono text-xs font-normal text-screen-dim">{s.subtitle}</span>
        </p>
        {!drawFailed && (
          <p className="hidden text-right font-mono text-xs leading-relaxed text-screen-dim sm:block">
            {readout(IMATINIB, t).join(" · ")}
            {canDrag && <span className="block">{s.drag}</span>}
          </p>
        )}
      </div>

      <div className="pointer-events-none relative z-10 mt-auto flex flex-wrap items-end justify-between gap-6 px-6 pt-[46svh] pb-8 md:px-12 md:pt-0 md:pb-12">
        <div className="pointer-events-auto max-w-xl">{children}</div>
        {!drawFailed && (
          <div className="pointer-events-auto flex items-center gap-1.5">
            <ModeSwitch mode={mode} onChange={setMode} />
            {mode !== "molecule" && !reduceMotion && (
              <button
                type="button"
                aria-label={t.structure.replay}
                title={t.structure.replay}
                onClick={() => viewer.current?.replay()}
                className="inline-flex size-8 items-center justify-center rounded-md border border-screen-dim/50 bg-screen-ink/8 hover:bg-screen-ink/15 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-screen-ink"
              >
                <Play className="size-3.5" />
              </button>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

function ModeSwitch({ mode, onChange }: { mode: ViewMode; onChange: (mode: ViewMode) => void }) {
  const t = useMessages();
  return (
    <div
      role="group"
      aria-label={t.structure.modeSwitch}
      className="inline-flex rounded-lg border border-screen-dim/50 bg-screen-ink/8 p-0.5"
    >
      {MODES.map((option) => (
        <button
          key={option}
          type="button"
          aria-pressed={mode === option}
          onClick={() => onChange(option)}
          className={cn(
            "rounded-md px-2.5 py-1 text-xs focus-visible:outline-2 focus-visible:outline-screen-ink",
            mode === option ? "bg-screen-ink text-screen" : "text-screen-dim hover:text-screen-ink",
          )}
        >
          {t.structure.modes[option]}
        </button>
      ))}
    </div>
  );
}

/** A ref for the element that scales from SMALLEST at the top of the page to full size once the
 * page has scrolled one screen down. Reduced motion keeps it as it is. */
function useScrollZoom(off: boolean): RefObject<HTMLDivElement | null> {
  const element = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const zoomed = element.current;
    if (off || !zoomed) return;
    let frame = 0;
    const update = () => {
      frame = 0;
      const progress = Math.min(Math.max(window.scrollY / window.innerHeight, 0), 1);
      zoomed.style.transform = `scale(${SMALLEST + (1 - SMALLEST) * progress})`;
    };
    const onScroll = () => {
      frame ||= requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(frame);
    };
  }, [off]);
  return element;
}
