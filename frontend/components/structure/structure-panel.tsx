"use client";

import { cn } from "cn";
import { Maximize2, Play, RotateCcw, X } from "lucide-react";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type ElementType,
  type ReactNode,
  type RefObject,
} from "react";

import { Dialog, DialogClose, DialogContent, DialogTitle } from "@/components/ui/dialog";
import { ApiError, getComplex, getStructure } from "@/lib/api";
import { coordinationBonds } from "@/lib/complex-scene";
import { structureSubtitle, structureTitle, type StructureTarget } from "@/lib/tool-cards";
import { useMediaQuery } from "@/lib/use-media-query";

import { readout } from "./readout";
import { COLORS, type SceneData, type ViewMode } from "./scene";
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

const ON_SCREEN =
  "rounded-md border border-screen-dim/50 bg-screen-ink/8 text-screen-ink hover:bg-screen-ink/15 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-screen-ink";
const TOOL = `${ON_SCREEN} inline-flex size-8 items-center justify-center`;

/**
 * The 3D view of a drug the answer looked up, in the evidence panel: the drug in its target's
 * binding site when Molecula has a reviewed complex, else the molecule alone. It is drawn as an
 * instrument's screen, dark in both themes, with the title, the switch and a readout of counts on
 * it (#297).
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

  if (loaded.status === "missing") {
    return (
      <section aria-label={`3D view of ${target.name}`} className="flex flex-col gap-1">
        <span className="font-medium">{title}</span>
        <p className="text-sm text-ink-2">
          No 3D model: Molecula has them for small-molecule drugs only, and {target.name} is too
          large.
        </p>
      </section>
    );
  }

  const heading = (Title: ElementType) => (
    <Title className="text-[15px] leading-snug font-semibold text-screen-ink">
      {title}
      <span className="block text-xs font-normal text-screen-dim">{subtitle}</span>
    </Title>
  );

  const modeSwitch = switchable && (
    <div
      role="group"
      aria-label="What the 3D view shows"
      className="inline-flex rounded-lg border border-screen-dim/50 bg-screen-ink/8 p-0.5"
    >
      {MODES.map((option) => (
        <button
          key={option.mode}
          type="button"
          aria-pressed={mode === option.mode}
          onClick={() => setMode(option.mode)}
          className={cn(
            "rounded-md px-2.5 py-1 text-xs focus-visible:outline-2 focus-visible:outline-screen-ink",
            mode === option.mode
              ? "bg-screen-ink text-screen"
              : "text-screen-dim hover:text-screen-ink",
          )}
        >
          {option.label}
        </button>
      ))}
    </div>
  );

  const replayable = switchable && mode !== "molecule" && !reduceMotion;

  const counts = ready && <Readout lines={readout(ready)} />;

  const legend = ready && (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-2">
      {switchable && mode !== "molecule" && (
        <>
          <LegendItem
            swatch={<span className="size-2.5 rounded-full" style={fill(COLORS.screen.drug)} />}
          >
            {target.name}
          </LegendItem>
          <LegendItem
            swatch={
              <span className="w-4 border-t-2 border-dashed" style={line(COLORS.screen.hbond)} />
            }
          >
            hydrogen bond
          </LegendItem>
          {coordinationBonds(complex).length > 0 && (
            <LegendItem
              swatch={
                <span
                  className="w-4 border-t-2 border-dashed"
                  style={line(COLORS.screen.coordination)}
                />
              }
            >
              metal bond
            </LegendItem>
          )}
          {complex.cofactors.length > 0 && (
            <LegendItem
              swatch={<span className="w-4 border-t-2" style={line(COLORS.screen.cofactor)} />}
            >
              cofactor
            </LegendItem>
          )}
          <LegendItem
            swatch={<span className="w-4 border-t-2" style={line(COLORS.screen.pocket)} />}
          >
            residues within 4 Å
          </LegendItem>
          {mode === "protein" && (
            <LegendItem
              swatch={<span className="w-4 border-t-4" style={line(COLORS.screen.trace)} />}
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
      className="flex scroll-mt-4 flex-col gap-2"
    >
      {target.complex?.caption && (
        <p className="rounded-md border border-rule-2 bg-panel px-3 py-2 text-sm text-ink">
          {target.complex.caption}
        </p>
      )}
      <Screen
        heading={heading("div")}
        tools={
          ready && (
            <ViewTools handle={viewer} replayable={replayable}>
              <Tool label="Full screen" onClick={() => setFullScreen(true)}>
                <Maximize2 />
              </Tool>
            </ViewTools>
          )
        }
        modeSwitch={modeSwitch}
        readout={counts}
        className="aspect-square max-h-[70dvh] w-full"
      >
        {ready ? (
          <StructureViewer
            ref={viewer}
            data={ready}
            mode={mode}
            label={`${title}, in 3D`}
            onError={failed}
            className="size-full"
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
      </Screen>
      {legend}
      {ready && (
        <Dialog open={fullScreen} onOpenChange={setFullScreen}>
          <DialogContent
            showCloseButton={false}
            className="flex h-[90dvh] max-w-6xl flex-col gap-3 bg-background p-4 sm:max-w-6xl"
          >
            <Screen
              heading={heading(DialogTitle)}
              tools={
                <ViewTools handle={fullScreenViewer} replayable={replayable}>
                  <DialogClose className={TOOL} aria-label="Close" title="Close">
                    <X className="size-4" />
                  </DialogClose>
                </ViewTools>
              }
              modeSwitch={modeSwitch}
              readout={counts}
              className="min-h-0 flex-1"
            >
              <StructureViewer
                ref={fullScreenViewer}
                data={ready}
                mode={mode}
                label={`${title}, in 3D`}
                onError={failed}
                className="size-full"
              />
            </Screen>
            {legend}
          </DialogContent>
        </Dialog>
      )}
    </section>
  );
}

/** The dark screen: the view fills it, with the title and tools along the top and the switch and
 * readout along the bottom, inside a viewfinder's corner marks. */
function Screen({
  heading,
  tools,
  modeSwitch,
  readout,
  className,
  children,
}: {
  heading: ReactNode;
  tools: ReactNode;
  modeSwitch: ReactNode;
  readout: ReactNode;
  className: string;
  children: ReactNode;
}) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-[10px] border border-rule-2 bg-screen text-screen-ink",
        className,
      )}
    >
      <div className="absolute inset-0">{children}</div>
      {/* The fades keep the text readable where the protein reaches under it. */}
      <div className="pointer-events-none absolute inset-x-0 top-0 flex items-start justify-between gap-3 bg-linear-to-b from-screen from-40% to-transparent px-6 pt-5 pb-8">
        <div className="min-w-0">{heading}</div>
        <div className="pointer-events-auto flex flex-none gap-1.5">{tools}</div>
      </div>
      <div className="pointer-events-none absolute inset-x-0 bottom-0 flex items-end justify-between gap-3 bg-linear-to-t from-screen from-40% to-transparent px-6 pt-8 pb-5">
        <div className="pointer-events-auto">{modeSwitch}</div>
        {readout}
      </div>
      <div aria-hidden className="viewfinder pointer-events-none absolute inset-3" />
    </div>
  );
}

/** Replay binding and Reset view for the view behind `handle`, then `children`. */
function ViewTools({
  handle,
  replayable,
  children,
}: {
  handle: RefObject<StructureViewerHandle | null>;
  replayable: boolean;
  children: ReactNode;
}) {
  return (
    <>
      {replayable && (
        <Tool label="Replay binding" onClick={() => handle.current?.replay()}>
          <Play />
        </Tool>
      )}
      <Tool label="Reset view" onClick={() => handle.current?.reset()}>
        <RotateCcw />
      </Tool>
      {children}
    </>
  );
}

function Tool({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      onClick={onClick}
      className={cn(TOOL, "[&_svg]:size-4")}
    >
      {children}
    </button>
  );
}

/** The counts in the lower right of the screen, the first one marked in the drug's colour. */
function Readout({ lines }: { lines: string[] }) {
  if (lines.length === 0) return null;
  return (
    <p className="flex flex-col items-end gap-px font-mono text-[10px] tracking-[0.06em] text-screen-dim uppercase">
      {lines.map((text, i) => (
        <span key={text} className="inline-flex items-center gap-1.5">
          {i === 0 && (
            <span
              aria-hidden
              className="size-[5px] rounded-full"
              style={fill(COLORS.screen.drug)}
            />
          )}
          {text}
        </span>
      ))}
    </p>
  );
}

const fill = (color: string): CSSProperties => ({ backgroundColor: color });
const line = (color: string): CSSProperties => ({ borderColor: color });

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
    <div className="flex size-full items-center justify-center p-6 text-center text-sm text-screen-dim">
      {loaded.status === "loading" && <p role="status">Loading the 3D structure…</p>}
      {loaded.status === "failed" && (
        <div role="alert">
          <p>The 3D structure couldn&apos;t be loaded.</p>
          <button
            type="button"
            className={cn(ON_SCREEN, "mt-2 px-3 py-1 text-sm")}
            onClick={onRetry}
          >
            Try again
          </button>
        </div>
      )}
    </div>
  );
}
