import { type ReactNode, useState } from "react";

import type { InputCategory, LabelUpdateStatus, Stats } from "@/lib/api";
import { CATEGORY_LABELS, ERROR_LABELS, compact, longDate, ranked } from "@/lib/stats";
import { cn } from "cn";

export function Card({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="min-w-0 rounded-xl border border-rule bg-card p-4">
      <h2 className="mb-3 text-sm font-semibold text-ink-2">{title}</h2>
      {children}
    </section>
  );
}

/** Horizontal bars in one colour, longest first, each with its count at the end. */
function BarList({ counts, mono }: { counts: [string, number][]; mono?: boolean }) {
  const most = Math.max(...counts.map(([, n]) => n));
  return (
    <dl className="grid grid-cols-[minmax(5.5rem,max-content)_1fr_auto] items-center gap-x-2.5 gap-y-1.5 text-[0.8125rem]">
      {counts.map(([name, n]) => (
        <div key={name} className="contents">
          <dt className={cn("truncate text-ink-2", mono && "font-mono text-xs")}>{name}</dt>
          <dd aria-hidden className="h-2.5">
            <span
              className="block h-2.5 min-w-0.5 rounded-r-[4px] bg-usage-bar"
              style={{ width: `${(n / most) * 100}%` }}
            />
          </dd>
          <dd className="text-right tabular-nums">{n.toLocaleString("en-GB")}</dd>
        </div>
      ))}
    </dl>
  );
}

function Quiet({ children }: { children: ReactNode }) {
  return <p className="py-1 text-[0.8125rem] text-ink-3">{children}</p>;
}

export function ToolCalls({ counts }: { counts: Record<string, number> }) {
  const list = ranked(counts);
  return (
    <Card title="Tool calls">
      {list.length ? <BarList counts={list} mono /> : <Quiet>No tool calls in this range.</Quiet>}
    </Card>
  );
}

/** How many questions the guard passed to the agent, then bars for the ones it answered itself. */
export function GuardSorting({ counts }: { counts: Partial<Record<InputCategory, number>> }) {
  const list = ranked(counts);
  const total = list.reduce((a, [, n]) => a + n, 0);
  const fixed = list.filter(([category]) => category !== "ok");
  return (
    <Card title="How the guard sorted questions">
      {total ? (
        <>
          <p className="mb-3 text-[0.8125rem] text-ink-2">
            <b className="block text-2xl font-semibold tracking-tight text-foreground">
              {(counts.ok ?? 0).toLocaleString("en-GB")} of {total.toLocaleString("en-GB")}
            </b>
            went to the agent as medicine questions
          </p>
          {fixed.length ? (
            <>
              <p className="mb-1.5 text-xs text-ink-3">The rest got a fixed answer:</p>
              <BarList counts={fixed.map(([category, n]) => [CATEGORY_LABELS[category], n])} />
            </>
          ) : (
            <Quiet>None got a fixed answer.</Quiet>
          )}
        </>
      ) : (
        <Quiet>No questions sorted in this range.</Quiet>
      )}
    </Card>
  );
}

export function Errors({ counts }: { counts: Stats["usage"]["errors"] }) {
  const list = ranked(counts).map(([kind, n]): [string, number] => [ERROR_LABELS[kind], n]);
  return (
    <Card title="Errors">
      {list.length ? <BarList counts={list} /> : <Quiet>No errors in this range.</Quiet>}
    </Card>
  );
}

/** What the store holds, in one line that wraps, with when the labels were last fetched and
 * updated, and the Update now button when the backend allows it. */
export function KnowledgeBase({
  kb,
  labelUpdate,
  onUpdate,
}: {
  kb: Stats["knowledge_base"];
  labelUpdate: LabelUpdateStatus;
  onUpdate: () => Promise<void>;
}) {
  const [problem, setProblem] = useState(false);
  const items: [string, string][] = [
    [compact(kb.drugs), "drugs"],
    [compact(kb.labels), "labels"],
    [compact(kb.label_sections), "label sections"],
    [compact(kb.chunks), "label passages"],
    [compact(kb.targets), "targets"],
    [compact(kb.conformers), "3D drug shapes"],
    [compact(kb.complexes), "drug–target structures"],
  ];
  const last = labelUpdate.last_run;

  function update() {
    setProblem(false);
    onUpdate().catch(() => setProblem(true));
  }

  return (
    <section
      aria-labelledby="knowledge-base"
      className="rounded-xl border border-rule bg-card px-4 py-3"
    >
      <div className="mb-1.5 flex items-center justify-between gap-3">
        <h2 id="knowledge-base" className="text-sm font-semibold text-ink-2">
          Knowledge base
        </h2>
        {labelUpdate.can_start && (
          <button
            type="button"
            onClick={update}
            disabled={labelUpdate.running}
            className="rounded-md border border-rule px-2.5 py-1 text-xs text-ink-2 hover:text-foreground disabled:opacity-60 disabled:hover:text-ink-2"
          >
            {labelUpdate.running ? "Updating…" : "Update now"}
          </button>
        )}
      </div>
      <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-ink-2">
        {items.map(([value, label]) => (
          <li key={label}>
            <b className="font-semibold text-foreground">{value}</b> {label}
          </li>
        ))}
      </ul>
      <ul className="mt-1.5 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-3">
        <li>
          Labels fetched{" "}
          {kb.labels_fetched_to
            ? longDate(kb.labels_fetched_to)
            : "not yet, the labels aren't built"}
        </li>
        {labelUpdate.running ? (
          <li role="status">Updating the labels…</li>
        ) : (
          last && (
            <li>
              Last label update {longDate(last.finished_at)}: {updateResult(last)}
            </li>
          )
        )}
        <li>Store schema v{kb.schema_version}</li>
      </ul>
      {problem && (
        <p role="alert" className="mt-1.5 text-xs text-red-700 dark:text-red-400">
          Could not start the update. Check that the backend is running.
        </p>
      )}
    </section>
  );
}

function updateResult(run: NonNullable<LabelUpdateStatus["last_run"]>): string {
  const drugs = `${run.drugs_changed} ${run.drugs_changed === 1 ? "drug" : "drugs"} changed`;
  switch (run.outcome) {
    case "complete":
      return run.drugs_changed ? drugs : "no label changed";
    case "nothing_new":
      return "nothing new on openFDA";
    case "incomplete":
      return `${drugs}, some drugs not checked (see the backend log)`;
    case "failed":
      return "failed (see the backend log)";
  }
}
