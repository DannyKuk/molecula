"use client";

import { Tabs } from "@base-ui/react/tabs";
import { cn } from "cn";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";

import type { Turn } from "@/lib/chat-turn";
import { citedRefs, excerpt, isLabel, labelDate, siteName, sourceLabel } from "@/lib/citations";
import {
  defaultTab,
  type EvidenceTab,
  type Shown,
  shownSteps,
  sourceCards,
  structuresInChat,
} from "@/lib/evidence";
import { structuresOf } from "@/lib/tool-cards";

import { OpenFdaCredit } from "./answer-sources";
import { ProgressSteps } from "./progress-steps";
import { StructurePanel } from "./structure/structure-panel";
import { ShowStructure } from "./tool-cards/view-in-3d";

type EvidencePanelProps = {
  turns: Turn[];
  /** What to show, with `turn` already resolved to an index. */
  shown: Shown & { turn: number };
  onShow: (shown: Shown) => void;
  /** Goes back to the answer coming in, set while the panel shows another one. */
  backToLive?: () => void;
  /** A close button, when the panel is a sheet. */
  close?: ReactNode;
};

const TAB =
  "inline-flex items-center gap-1.5 border-b-2 border-transparent px-3 pt-2 pb-2.5 text-[13px] text-ink-2 hover:text-ink focus-visible:outline-2 focus-visible:outline-ink-3 data-[active]:border-signal data-[active]:text-ink";

const NAV =
  "grid size-7 place-items-center rounded-md border border-rule-2 bg-card text-ink-2 hover:text-ink focus-visible:outline-2 focus-visible:outline-ink-3 disabled:opacity-35";

/** The 3D view, the sources and the steps of one answer, beside the chat or in a sheet. */
export function EvidencePanel({ turns, shown, onShow, backToLive, close }: EvidencePanelProps) {
  const index = shown.turn;
  const turn = turns[index];
  const steps = shownSteps(turn);
  const show = (to: number) => onShow({ turn: to, tab: defaultTab(turns[to]) });

  return (
    <Tabs.Root
      value={shown.tab}
      onValueChange={(tab: EvidenceTab) => onShow({ turn: index, tab })}
      className="flex min-h-0 flex-1 flex-col"
    >
      <div className="flex-none border-b border-rule px-4 pt-3">
        <div className="flex min-h-[30px] items-center gap-2">
          <h2 className="font-mono text-[11px] tracking-wider whitespace-nowrap text-signal uppercase">
            Answer {index + 1} of {turns.length}
          </h2>
          <p className="min-w-0 flex-1 truncate text-sm text-ink">{turn.question}</p>
          {backToLive && (
            <button
              type="button"
              onClick={backToLive}
              className="inline-flex h-7 items-center gap-1.5 rounded-full border border-signal px-2.5 text-xs font-medium whitespace-nowrap text-signal hover:bg-signal-soft focus-visible:outline-2 focus-visible:outline-ink-3"
            >
              <span aria-hidden className="size-1.5 animate-pulse rounded-full bg-signal" />
              Live answer
            </button>
          )}
          <button
            type="button"
            aria-label="Previous answer"
            disabled={index === 0}
            onClick={() => show(index - 1)}
            className={NAV}
          >
            <ChevronLeft aria-hidden className="size-4" />
          </button>
          <button
            type="button"
            aria-label="Next answer"
            disabled={index === turns.length - 1}
            onClick={() => show(index + 1)}
            className={NAV}
          >
            <ChevronRight aria-hidden className="size-4" />
          </button>
          {close}
        </div>
        <Tabs.List aria-label="Evidence" className="mt-2 flex gap-0.5">
          <Tabs.Tab value="3d" className={TAB}>
            3D
            {shown.fresh && (
              <>
                <span aria-hidden className="size-1.5 rounded-full bg-signal" />
                <span className="sr-only">, new</span>
              </>
            )}
          </Tabs.Tab>
          <Tabs.Tab value="sources" className={TAB}>
            Sources
            {turn.sources && <Count>{sourceCards(turn.sources).length}</Count>}
          </Tabs.Tab>
          <Tabs.Tab value="steps" className={TAB}>
            Steps
            <Count>{steps.length}</Count>
          </Tabs.Tab>
        </Tabs.List>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        <Tabs.Panel value="3d">
          <StructureTab turns={turns} index={index} cid={shown.cid} onShow={onShow} />
        </Tabs.Panel>
        <Tabs.Panel value="sources">
          <SourcesTab turn={turn} highlighted={shown.refs ?? []} />
        </Tabs.Panel>
        <Tabs.Panel value="steps">
          <ShowStructure value={(cid) => onShow({ turn: index, tab: "3d", cid })}>
            {turn.steps.length > 0 ? (
              <ProgressSteps
                steps={turn.steps}
                live={turn.state === "answering"}
                answer={turn.answer}
              />
            ) : (
              <Empty>
                {turn.state === "answering" || turn.state === "queued"
                  ? "Thinking…"
                  : "Molecula answered this without looking anything up."}
              </Empty>
            )}
          </ShowStructure>
        </Tabs.Panel>
      </div>
    </Tabs.Root>
  );
}

function StructureTab({
  turns,
  index,
  cid,
  onShow,
}: {
  turns: Turn[];
  index: number;
  cid?: number;
  onShow: (shown: Shown) => void;
}) {
  const turn = turns[index];
  const targets = structuresOf(turn.steps);
  const target = targets.find((candidate) => candidate.cid === cid) ?? targets[0];
  const inChat = structuresInChat(turns);
  return (
    <div className="flex flex-col gap-4">
      {targets.length > 1 && (
        <div
          role="group"
          aria-label="Drug in 3D"
          className="inline-flex self-start rounded-lg bg-card p-0.5"
        >
          {targets.map((option) => (
            <button
              key={option.cid}
              type="button"
              aria-pressed={option === target}
              onClick={() => onShow({ turn: index, tab: "3d", cid: option.cid })}
              className={cn(
                "rounded-md px-3 py-1 text-sm focus-visible:outline-2 focus-visible:outline-ink-3",
                option === target ? "bg-ink text-page" : "text-ink-2 hover:text-ink",
              )}
            >
              {option.name}
            </button>
          ))}
        </div>
      )}
      {target ? (
        // Keyed by answer, so each answer's view is built afresh and plays its binding.
        <StructurePanel key={`${index}:${target.cid}`} target={target} />
      ) : (
        <Empty>
          {turn.state === "answering"
            ? "Looking things up… a structure shows here if this answer finds one."
            : "This answer didn't look up a structure."}
        </Empty>
      )}
      {inChat.length > 0 && (
        <section aria-label="Structures in this chat" className="flex flex-col gap-2">
          <h3 className="font-mono text-[11px] tracking-wider text-ink-3 uppercase">
            Structures in this chat
          </h3>
          <ul className="flex flex-wrap gap-1.5">
            {inChat.map((structure) => {
              const current = structure.turn === index && structure.target === target;
              return (
                <li key={`${structure.turn}:${structure.target.cid}`}>
                  <button
                    type="button"
                    aria-current={current || undefined}
                    onClick={() =>
                      onShow({ turn: structure.turn, tab: "3d", cid: structure.target.cid })
                    }
                    className={cn(
                      "inline-flex items-baseline gap-1.5 rounded-md border bg-card px-2.5 py-1 text-[12.5px] focus-visible:outline-2 focus-visible:outline-ink-3",
                      current ? "border-signal" : "border-rule-2 hover:border-ink-3",
                    )}
                  >
                    {structure.target.name}
                    <span className="font-mono text-[11px] text-ink-3">
                      {structure.target.complex?.pdb_id ?? "molecule"} · answer {structure.turn + 1}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        </section>
      )}
    </div>
  );
}

function SourcesTab({ turn, highlighted }: { turn: Turn; highlighted: number[] }) {
  const list = useRef<HTMLOListElement>(null);
  const highlightKey = highlighted.join(",");
  useEffect(() => {
    if (!highlightKey) return;
    list.current
      ?.querySelector("[data-highlighted]")
      ?.scrollIntoView?.({ block: "nearest", behavior: "smooth" });
  }, [highlightKey]);

  if (!turn.sources) {
    return (
      <Empty>
        {turn.state === "answering" || turn.state === "queued"
          ? "The sources show here once the answer is written."
          : "This answer has no sources."}
      </Empty>
    );
  }
  const cards = sourceCards(turn.sources);
  if (cards.length === 0) return <Empty>This answer used no sources.</Empty>;
  const cited = new Set(citedRefs(turn.answer));
  return (
    <div className="flex flex-col gap-3">
      <ol ref={list} aria-label="Sources of this answer" className="flex flex-col gap-2">
        {cards.map(({ source, refs }) => {
          const lit = refs.some((ref) => highlighted.includes(ref));
          const text = isLabel(source) ? turn.passages[refs[0]]?.text : undefined;
          return (
            <li
              key={refs.join(",") || source.url}
              data-highlighted={lit || undefined}
              className={cn(
                "flex flex-col gap-1 rounded-lg border p-3 text-sm transition-colors duration-500",
                lit ? "border-signal bg-signal-soft" : "border-rule bg-card",
              )}
            >
              <p className="flex items-baseline gap-2">
                {refs.length > 0 && (
                  <span className="font-mono text-[11px] text-signal">[{refs.join(", ")}]</span>
                )}
                <span className="font-medium">{sourceLabel(source)}</span>
                {refs.some((ref) => cited.has(ref)) && (
                  <span className="font-mono text-[10px] tracking-wider text-ink-3 uppercase">
                    Cited
                  </span>
                )}
              </p>
              {source.effective_time && (
                <p className="text-xs text-ink-3">
                  FDA label of {labelDate(source.effective_time)}
                </p>
              )}
              {text && <p className="border-l-2 border-signal pl-2 text-ink-2">{excerpt(text)}</p>}
              <a
                href={source.url}
                target="_blank"
                rel="noopener noreferrer"
                className="self-start text-[12.5px] font-medium underline underline-offset-4"
              >
                {isLabel(source) ? "Open the label on DailyMed" : `Open on ${siteName(source)}`}
              </a>
            </li>
          );
        })}
      </ol>
      {cards.some(({ source }) => isLabel(source)) && <OpenFdaCredit />}
    </div>
  );
}

function Count({ children }: { children: number }) {
  return <span className="font-mono text-[11px] text-ink-3">{children}</span>;
}

function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="rounded-lg border border-dashed border-rule-2 px-4 py-6 text-center text-sm text-ink-2">
      {children}
    </p>
  );
}
