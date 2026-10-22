"use client";

import { cn } from "cn";
import { Fragment, memo, useState, type KeyboardEvent, type PointerEvent } from "react";

import {
  type Benchmark,
  type Model,
  type Rank,
  type Scope,
  SCOPES,
  hitsInGroup,
  isHit,
  rankBand,
  rankText,
  sectionName,
} from "@/lib/embedding-benchmark";

import { RankDot } from "./dots";
import { FloatingTip, type TipAt } from "./floating-tip";

const GROUP_SHORT = { cpu: "Local CPU", gpu: "GPU", cloud: "Cloud" };

export type GridSelection = { question: number; model: string | null };

type HitGridProps = {
  benchmark: Benchmark;
  scope: Scope;
  selected: GridSelection | null;
  onQuestion: (question: number, model: string | null) => void;
  onModel: (label: string) => void;
};

/** Questions × models, grouped by section group; each dot is where the answer ranked. */
export function HitGrid(props: HitGridProps) {
  const [tip, setTip] = useState<(TipAt & { question: number; label: string }) | null>(null);

  function hover(event: PointerEvent<HTMLDivElement>) {
    const cell = (event.target as HTMLElement).closest<HTMLElement>("[data-cell]")?.dataset.cell;
    if (!cell) return setTip(null);
    const split = cell.indexOf(":");
    const question = Number(cell.slice(0, split));
    setTip({ x: event.clientX, y: event.clientY, question, label: cell.slice(split + 1) });
  }

  return (
    <div
      className="max-h-[70vh] max-w-full overflow-auto lg:max-h-[calc(100vh-140px)]"
      onPointerMove={hover}
      onPointerLeave={() => setTip(null)}
    >
      <GridTable {...props} />
      {tip && <CellTip benchmark={props.benchmark} scope={props.scope} {...tip} />}
    </div>
  );
}

// Memoized so that moving the pointer over a thousand dots redraws only the tooltip.
const GridTable = memo(function GridTable({
  benchmark,
  scope,
  selected,
  onQuestion,
  onModel,
}: HitGridProps) {
  const { models, sections } = benchmark;
  const order = sections.flatMap((s) => s.questions.map((q) => q.index));
  const [focus, setFocus] = useState<[row: number, col: number]>([0, 0]);
  const rank = (label: string, question: number): Rank => benchmark.ranks[label][scope][question];
  const separatorBefore = (m: Model) =>
    m !== models[0] && m.group !== models[models.indexOf(m) - 1].group;
  const groups = [...new Set(models.map((m) => m.group))].map((group) => ({
    group,
    size: models.filter((m) => m.group === group).length,
  }));

  function moveFocus(event: KeyboardEvent) {
    const steps: Record<string, [number, number]> = {
      ArrowUp: [-1, 0],
      ArrowDown: [1, 0],
      ArrowLeft: [0, -1],
      ArrowRight: [0, 1],
    };
    const step = steps[event.key];
    if (!step || !(event.target as HTMLElement).dataset.cell) return;
    event.preventDefault();
    const row = Math.min(order.length - 1, Math.max(0, focus[0] + step[0]));
    const col = Math.min(models.length - 1, Math.max(0, focus[1] + step[1]));
    setFocus([row, col]);
    const cell = event.currentTarget.querySelector<HTMLElement>(
      `[data-cell="${order[row]}:${models[col].label}"]`,
    );
    cell?.focus();
  }

  return (
    <table className="border-separate border-spacing-0 text-xs" onKeyDown={moveFocus}>
      <thead>
        <tr>
          <th className="sticky left-0 z-[3] bg-background" />
          {groups.map(({ group, size }, i) => (
            <Fragment key={group}>
              {i > 0 && <th className="w-2 min-w-2" />}
              <th
                colSpan={size}
                className="max-w-0 pt-1.5 pl-0.5 text-left font-mono text-[10px] font-medium tracking-wide whitespace-nowrap text-ink-3 uppercase"
              >
                {GROUP_SHORT[group]}
              </th>
            </Fragment>
          ))}
        </tr>
        <tr>
          <th className="sticky top-0 left-0 z-[3] bg-background px-2 text-left align-bottom text-xs font-normal text-ink-2">
            Question
          </th>
          {models.map((m) => (
            <Fragment key={m.label}>
              {separatorBefore(m) && <th className="sticky top-0 z-[2] w-2 bg-background" />}
              <th className="sticky top-0 z-[2] h-[118px] w-[22px] bg-background p-0 align-bottom">
                <button
                  type="button"
                  title={m.name}
                  aria-label={`Open ${m.name}`}
                  onClick={() => onModel(m.label)}
                  className={cn(
                    "rotate-180 py-1.5 text-[0.72rem] font-medium whitespace-nowrap text-ink-2 [writing-mode:vertical-rl] hover:text-foreground hover:underline",
                    m.isApp &&
                      "font-semibold text-app-model-foreground dark:text-app-model-foreground",
                  )}
                >
                  {m.short}
                </button>
              </th>
            </Fragment>
          ))}
        </tr>
      </thead>
      <tbody>
        {sections.map((section) => (
          <Fragment key={section.id}>
            <tr>
              <th
                scope="row"
                className="sticky left-0 z-[1] border-t border-rule-2 bg-background px-2 pt-3 pb-1 text-left text-xs font-semibold"
              >
                {section.name} ({section.questions.length})
              </th>
              {models.map((m) => {
                const hits = hitsInGroup(benchmark.ranks[m.label][scope], section);
                return (
                  <Fragment key={m.label}>
                    {separatorBefore(m) && <td className="border-t border-rule-2" />}
                    <td
                      title={`${m.name}: ${hits} of ${section.questions.length} in the top 5`}
                      className="border-t border-rule-2 pt-3 text-center align-bottom text-[10px] text-ink-3 tabular-nums"
                    >
                      {hits}
                    </td>
                  </Fragment>
                );
              })}
            </tr>
            {section.questions.map((q) => {
              const rowSelected = selected?.question === q.index;
              return (
                <tr key={q.index} className="group/row">
                  <td
                    className={cn(
                      "sticky left-0 z-[1] bg-background group-hover/row:bg-panel",
                      rowSelected && "shadow-[inset_3px_0_0_var(--signal)]",
                    )}
                  >
                    <button
                      type="button"
                      title={q.question}
                      onClick={() => onQuestion(q.index, null)}
                      className="block w-24 truncate px-2 text-left text-xs/5 sm:w-[250px]"
                    >
                      {q.drug}
                      <span className="hidden text-ink-2 sm:inline"> · {q.question}</span>
                    </button>
                  </td>
                  {models.map((m, col) => {
                    const r = rank(m.label, q.index);
                    const row = order.indexOf(q.index);
                    const cellSelected = rowSelected && selected?.model === m.label;
                    return (
                      <Fragment key={m.label}>
                        {separatorBefore(m) && <td />}
                        <td
                          className={cn(
                            "h-5 w-[22px] p-0 group-hover/row:bg-panel",
                            m.isApp && "bg-app-model/55",
                          )}
                        >
                          <button
                            type="button"
                            data-cell={`${q.index}:${m.label}`}
                            tabIndex={focus[0] === row && focus[1] === col ? 0 : -1}
                            aria-label={`${q.question} · ${m.name}: answer ${rankText(r)}`}
                            aria-pressed={cellSelected}
                            onClick={() => {
                              setFocus([row, col]);
                              onQuestion(q.index, m.label);
                            }}
                            className={cn(
                              "mx-auto my-0.5 flex size-4 items-center justify-center rounded-full outline-offset-0 hover:outline-1 hover:outline-ink-3 focus-visible:outline-2 focus-visible:outline-ink",
                              cellSelected &&
                                "outline-2 outline-signal hover:outline-2 hover:outline-signal",
                            )}
                          >
                            <RankDot band={rankBand(r)} />
                          </button>
                        </td>
                      </Fragment>
                    );
                  })}
                </tr>
              );
            })}
          </Fragment>
        ))}
      </tbody>
    </table>
  );
});

function CellTip({
  benchmark,
  scope,
  question,
  label,
  ...at
}: TipAt & { benchmark: Benchmark; scope: Scope; question: number; label: string }) {
  const q = benchmark.questions[question];
  const model = benchmark.models.find((m) => m.label === label);
  const rank = benchmark.ranks[label][scope][question];
  return (
    <FloatingTip at={at}>
      <div className="mb-1 font-semibold">{model?.name}</div>
      <div>{q.question}</div>
      <div className="mt-1">
        <b>{rank === null ? "Not in the top 10" : `Answer ${rankText(rank)}`}</b>
        {isHit(rank) ? " (a hit)" : " (a miss)"}
      </div>
      <div className="text-ink-2">
        {sectionName(q.section_group)} · {SCOPES[scope].toLowerCase()}
      </div>
    </FloatingTip>
  );
}
