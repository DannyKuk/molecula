"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";

import { Dialog, DialogClose, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { ApiError, getComplex, getStructure } from "@/lib/api";
import type { StructureTarget } from "@/lib/tool-cards";

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
  "rounded-md border border-zinc-300 px-3 py-1 text-sm hover:bg-zinc-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 dark:border-zinc-700 dark:hover:bg-zinc-900";

/**
 * The 3D view of a drug the answer looked up, under the answer: the drug in its target's binding
 * site when Molecula has a reviewed complex, else the molecule alone.
 */
export function StructurePanel({ target }: { target: StructureTarget }) {
  const [loaded, setLoaded] = useState<Loaded>({ status: "loading" });
  const [attempt, setAttempt] = useState(0);
  const [mode, setMode] = useState<ViewMode>(target.complex ? "site" : "molecule");
  const [fullScreen, setFullScreen] = useState(false);
  const viewer = useRef<StructureViewerHandle>(null);
  const hasComplex = target.complex !== null;

  useEffect(() => {
    const abort = new AbortController();
    const load: Promise<SceneData> = hasComplex
      ? getComplex(target.cid, abort.signal).then((complex) => ({ kind: "complex", complex }))
      : getStructure(target.cid, abort.signal).then((sdf) => ({ kind: "molecule", sdf }));
    load.then(
      (data) => setLoaded({ status: "ready", data }),
      (error: unknown) => {
        if (abort.signal.aborted) return;
        const missing = error instanceof ApiError && error.status === 404;
        setLoaded({ status: missing ? "missing" : "failed" });
      },
    );
    return () => abort.abort();
  }, [target.cid, hasComplex, attempt]);

  const name = target.name.charAt(0).toUpperCase() + target.name.slice(1);
  const title = target.complex
    ? `${name} in ${target.complex.target ?? `PDB ${target.complex.pdb_id}`}`
    : name;
  const ready = loaded.status === "ready" ? loaded.data : null;
  const switchable = ready?.kind === "complex";

  const modeSwitch = switchable && (
    <div
      role="group"
      aria-label="What the 3D view shows"
      className="inline-flex rounded-lg bg-zinc-100 p-0.5 dark:bg-zinc-900"
    >
      {MODES.map((option) => (
        <button
          key={option.mode}
          type="button"
          aria-pressed={mode === option.mode}
          onClick={() => setMode(option.mode)}
          className={`rounded-md px-3 py-1 text-sm focus-visible:outline-2 focus-visible:outline-zinc-500 ${
            mode === option.mode
              ? "bg-white shadow-sm dark:bg-zinc-700"
              : "text-zinc-600 hover:text-zinc-900 dark:text-zinc-400 dark:hover:text-zinc-100"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );

  const legend = ready && (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-zinc-600 dark:text-zinc-400">
      {switchable && mode !== "molecule" && (
        <>
          <LegendItem swatch={<span className="size-2.5 rounded-full bg-green-500" />}>
            {target.name}
          </LegendItem>
          <LegendItem swatch={<span className="w-4 border-t-2 border-dashed border-amber-500" />}>
            hydrogen bond
          </LegendItem>
          <LegendItem swatch={<span className="w-4 border-t-2 border-zinc-400" />}>
            residues within 4 Å
          </LegendItem>
          {mode === "protein" && (
            <LegendItem
              swatch={<span className="w-4 border-t-4 border-zinc-300 dark:border-zinc-600" />}
            >
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
      className="flex scroll-mt-4 flex-col gap-2 rounded-xl border border-zinc-200 p-3 dark:border-zinc-800"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <span className="font-medium">{title}</span>{" "}
          {loaded.status !== "missing" && (
            <span className="text-sm text-zinc-500">{subtitle(target)}</span>
          )}
        </div>
        {ready && (
          <div className="flex flex-wrap gap-2">
            {switchable && mode !== "molecule" && (
              <button type="button" className={BUTTON} onClick={() => viewer.current?.replay()}>
                Replay binding
              </button>
            )}
            <button type="button" className={BUTTON} onClick={() => viewer.current?.reset()}>
              Reset view
            </button>
            <button type="button" className={BUTTON} onClick={() => setFullScreen(true)}>
              Full screen
            </button>
          </div>
        )}
      </div>
      {target.complex?.caption && (
        <p className="rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-900 dark:border-sky-900 dark:bg-sky-950 dark:text-sky-200">
          {target.complex.caption}
        </p>
      )}
      {modeSwitch}
      {ready ? (
        <StructureViewer
          ref={viewer}
          data={ready}
          mode={mode}
          label={`${title}, in 3D`}
          className="h-[380px] rounded-lg border border-zinc-200 dark:border-zinc-800"
        />
      ) : (
        <Placeholder
          loaded={loaded}
          name={target.name}
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
                {title}{" "}
                <span className="text-sm font-normal text-zinc-500">{subtitle(target)}</span>
              </DialogTitle>
              <DialogClose className={BUTTON}>Close</DialogClose>
            </div>
            {modeSwitch}
            <StructureViewer
              data={ready}
              mode={mode}
              label={`${title}, in 3D`}
              className="min-h-0 flex-1 rounded-lg border border-zinc-200 dark:border-zinc-800"
            />
            {legend}
          </DialogContent>
        </Dialog>
      )}
    </section>
  );
}

function subtitle(target: StructureTarget): string {
  if (!target.complex) return "the molecule alone: no reviewed structure with its target";
  const { pdb_id, organism, hydrogen_bonds } = target.complex;
  const bonds = hydrogen_bonds.length;
  return [`PDB ${pdb_id}`, organism, `${bonds} hydrogen ${bonds === 1 ? "bond" : "bonds"}`]
    .filter(Boolean)
    .join(" · ");
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

function Placeholder({
  loaded,
  name,
  onRetry,
}: {
  loaded: Loaded;
  name: string;
  onRetry: () => void;
}) {
  return (
    <div className="flex h-[380px] items-center justify-center rounded-lg border border-dashed border-zinc-300 bg-zinc-50 p-6 text-center text-sm text-zinc-600 dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-400">
      {loaded.status === "loading" && <p role="status">Loading the 3D structure…</p>}
      {loaded.status === "missing" && (
        <div>
          <p className="font-medium text-zinc-900 dark:text-zinc-100">No 3D model of {name}</p>
          <p className="mt-1 max-w-sm">
            Molecula has 3D models of small-molecule drugs only. PubChem has none of {name}, which
            is too large, and one computed from its formula would mean little.
          </p>
        </div>
      )}
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
