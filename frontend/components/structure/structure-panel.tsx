"use client";

import { useCallback, useEffect, useRef, useState, type ReactNode, type RefObject } from "react";

import { Dialog, DialogClose, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { ApiError, getComplex, getStructure } from "@/lib/api";
import { coordinationBonds } from "@/lib/complex-scene";
import { structureSubtitle, structureTitle, type StructureTarget } from "@/lib/tool-cards";
import { useMediaQuery } from "@/lib/use-media-query";

import type { SceneData, ViewMode } from "./scene";
import { StructureViewer, type StructureViewerHandle } from "./structure-viewer";

type Loaded =
  | { status: "loading" }
  | { status: "ready"; data: SceneData }
  | { status: "missing" }
  | { status: "failed" };

const MODES: { mode: ViewMode; label: string }[] = [
  { mode: "molecule", label: "Molecule" },
  { mode: "site", label: "Binding site" },
  { mode: "protein", label: "Whole protein" },
];

const BUTTON =
  "rounded-md border border-rule-2 px-3 py-1 text-sm hover:bg-panel focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3";

/**
 * The 3D view of a drug the answer looked up, in the evidence panel: the drug in its target's
 * binding site when Molecula has a reviewed complex, else the molecule alone.
 */
export function StructurePanel({ target }: { target: StructureTarget }) {
  const [loaded, setLoaded] = useState<Loaded>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [mode, setMode] = useState<ViewMode>(target.complex ? "site" : "molecule");
  const [fullScreen, setFullScreen] = useState(false);
  const viewer = useRef<StructureViewerHandle>(null);
  const fullScreenViewer = useRef<StructureViewerHandle>(null);
  const hasComplex = target.complex !== null;
  const reduceMotion = useMediaQuery("(prefers-reduced-motion: reduce)");
  const failed = useCallback(() => {
    setFullScreen(false);
    setLoaded({ status: "failed" });
  }, []);

  useEffect(() => {
    const abort = new AbortController();
    const load: Promise<SceneData> = hasComplex
      ? getComplex(target.cid, abort.signal).then((complex) => ({ kind: "complex", complex }))
      : getStructure(target.cid, abort.signal).then((sdf) => ({ kind: "molecule", sdf }));
    load.then(
      (data) => setLoaded({ status: "ready", data }),
      (error: unknown) => {
        if (abort.signal.aborted) return;
        // A drug the tool found a complex for always has one, so only a missing conformer is "missing".
        const missing = !hasComplex && error instanceof ApiError && error.status === 404;
        setLoaded({ status: missing ? "missing" : "failed" });
      },
    );
    return () => abort.abort();
  }, [target.cid, hasComplex, attempt]);

  const title = structureTitle(target);
  const subtitle = structureSubtitle(target);
  const ready = loaded.status === "ready" ? loaded.data : null;
  const complex = ready?.kind === "complex" ? ready.complex : null;
  const switchable = complex !== null;

  const modeSwitch = switchable && (
    <div
      role="group"
      aria-label="What the 3D view shows"
      className="inline-flex rounded-lg bg-panel p-0.5"
    >
      {MODES.map((option) => (
        <button
          key={option.mode}
          type="button"
          aria-pressed={mode === option.mode}
          onClick={() => setMode(option.mode)}
          className={`rounded-md px-3 py-1 text-sm focus-visible:outline-2 focus-visible:outline-ink-3 ${
            mode === option.mode ? "bg-card shadow-sm" : "text-ink-2 hover:text-ink"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );

  const controls = (handle: RefObject<StructureViewerHandle | null>) => (
    <>
      {switchable && mode !== "molecule" && !reduceMotion && (
        <button type="button" className={BUTTON} onClick={() => handle.current?.replay()}>
          Replay binding
        </button>
      )}
      <button type="button" className={BUTTON} onClick={() => handle.current?.reset()}>
        Reset view
      </button>
    </>
  );

  const legend = ready && (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
      {switchable && mode !== "molecule" && (
        <>
          <LegendItem swatch={<span className="size-2.5 rounded-full bg-green-500" />}>
            {target.name}
          </LegendItem>
          <LegendItem swatch={<span className="w-4 border-t-2 border-dashed border-amber-500" />}>
            hydrogen bond
          </LegendItem>
          {coordinationBonds(complex).length > 0 && (
            <LegendItem
              swatch={<span className="w-4 border-t-2 border-dashed border-purple-500" />}
            >
              metal bond
            </LegendItem>
          )}
          {complex.cofactors.length > 0 && (
            <LegendItem swatch={<span className="w-4 border-t-2 border-cyan-500" />}>
              cofactor
            </LegendItem>
          )}
          <LegendItem swatch={<span className="w-4 border-t-2 border-ink-3" />}>
            residues within 4 Å
          </LegendItem>
          {mode === "protein" && (
            <LegendItem swatch={<span className="w-4 border-t-4 border-rule-2" />}>
              protein backbone
            </LegendItem>
          )}
        </>
      )}
      <span>Drag to turn · scroll to zoom</span>
    </div>
  );

  return (
    <section
      data-structure={target.cid}
      aria-label={`3D view of ${target.name}`}
      className="flex scroll-mt-4 flex-col gap-2 rounded-xl border border-rule p-3"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <span className="font-medium">{title}</span>{" "}
          {loaded.status !== "missing" && <span className="text-sm text-ink-3">{subtitle}</span>}
        </div>
        {ready && (
          <div className="flex flex-wrap gap-2">
            {controls(viewer)}
            <button type="button" className={BUTTON} onClick={() => setFullScreen(true)}>
              Full screen
            </button>
          </div>
        )}
      </div>
      {target.complex?.caption && (
        <p className="rounded-md border border-rule-2 bg-panel px-3 py-2 text-sm text-ink">
          {target.complex.caption}
        </p>
      )}
      {modeSwitch}
      {loaded.status === "missing" ? (
        <p className="text-sm text-ink-2">
          No 3D model: Molecula has them for small-molecule drugs only, and {target.name} is too
          large.
        </p>
      ) : ready ? (
        <StructureViewer
          ref={viewer}
          data={ready}
          mode={mode}
          label={`${title}, in 3D`}
          onError={failed}
          className="h-[380px] rounded-lg border border-rule bg-card"
        />
      ) : (
        <Placeholder
          loaded={loaded}
          onRetry={() => {
            setLoaded({ status: "loading" });
            setAttempt((n) => n + 1);
          }}
        />
      )}
      {legend}
      {ready && (
        <Dialog open={fullScreen} onOpenChange={setFullScreen}>
          <DialogContent
            showCloseButton={false}
            className="flex h-[90dvh] max-w-6xl flex-col gap-3 bg-background p-4 sm:max-w-6xl"
          >
            <div className="flex items-start justify-between gap-4">
              <DialogTitle className="font-medium">
                {title} <span className="text-sm font-normal text-ink-3">{subtitle}</span>
              </DialogTitle>
              <div className="flex flex-wrap justify-end gap-2">
                {controls(fullScreenViewer)}
                <DialogClose className={BUTTON}>Close</DialogClose>
              </div>
            </div>
            {modeSwitch}
            <StructureViewer
              ref={fullScreenViewer}
              data={ready}
              mode={mode}
              label={`${title}, in 3D`}
              onError={failed}
              className="min-h-0 flex-1 rounded-lg border border-rule bg-card"
            />
            {legend}
          </DialogContent>
        </Dialog>
      )}
    </section>
  );
}

function LegendItem({ swatch, children }: { swatch: ReactNode; children: ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span aria-hidden className="inline-flex">
        {swatch}
      </span>
      {children}
    </span>
  );
}

function Placeholder({ loaded, onRetry }: { loaded: Loaded; onRetry: () => void }) {
  return (
    <div className="flex h-[380px] items-center justify-center rounded-lg border border-dashed border-rule-2 bg-card p-6 text-center text-sm text-ink-2">
      {loaded.status === "loading" && <p role="status">Loading the 3D structure…</p>}
      {loaded.status === "failed" && (
        <div role="alert">
          <p>The 3D structure couldn&apos;t be loaded.</p>
          <button type="button" className={`${BUTTON} mt-2`} onClick={onRetry}>
            Try again
          </button>
        </div>
      )}
    </div>
  );
}
