import { type ReactNode, useState } from "react";

import type { InputCategory, LabelUpdateStatus, Stats } from "@/lib/api";
import { type Messages, useMessages } from "@/lib/messages";
import { compact, count, longDate, ranked } from "@/lib/stats";
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
  const t = useMessages();
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
          <dd className="text-right tabular-nums">{count(n, t)}</dd>
        </div>
      ))}
    </dl>
  );
}

function Quiet({ children }: { children: ReactNode }) {
  return <p className="py-1 text-[0.8125rem] text-ink-3">{children}</p>;
}

export function ToolCalls({ counts }: { counts: Record<string, number> }) {
  const t = useMessages();
  const list = ranked(counts);
  return (
    <Card title={t.dashboard.toolCalls}>
      {list.length ? <BarList counts={list} mono /> : <Quiet>{t.dashboard.noToolCalls}</Quiet>}
    </Card>
  );
}

/** How many questions the guard passed to the agent, then bars for the ones it answered itself. */
export function GuardSorting({ counts }: { counts: Partial<Record<InputCategory, number>> }) {
  const t = useMessages();
  const list = ranked(counts);
  const total = list.reduce((a, [, n]) => a + n, 0);
  const fixed = list.filter(([category]) => category !== "ok");
  return (
    <Card title={t.dashboard.guard}>
      {total ? (
        <>
          <p className="mb-3 text-[0.8125rem] text-ink-2">
            <b className="block text-2xl font-semibold tracking-tight text-foreground">
              {t.dashboard.okOfTotal(count(counts.ok ?? 0, t), count(total, t))}
            </b>
            {t.dashboard.wentToAgent}
          </p>
          {fixed.length ? (
            <>
              <p className="mb-1.5 text-xs text-ink-3">{t.dashboard.restFixed}</p>
              <BarList
                counts={fixed.map(([category, n]) => [t.dashboard.categories[category], n])}
              />
            </>
          ) : (
            <Quiet>{t.dashboard.noneFixed}</Quiet>
          )}
        </>
      ) : (
        <Quiet>{t.dashboard.noneSorted}</Quiet>
      )}
    </Card>
  );
}

export function Errors({ counts }: { counts: Stats["usage"]["errors"] }) {
  const t = useMessages();
  const list = ranked(counts).map(([kind, n]): [string, number] => [
    t.dashboard.errorKinds[kind],
    n,
  ]);
  return (
    <Card title={t.dashboard.errors}>
      {list.length ? <BarList counts={list} /> : <Quiet>{t.dashboard.noErrors}</Quiet>}
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
  const t = useMessages();
  const text = t.dashboard.knowledgeBase;
  const [problem, setProblem] = useState(false);
  const items: [string, string][] = [
    [compact(kb.drugs, t), text.drugs],
    [compact(kb.labels, t), text.labels],
    [compact(kb.label_sections, t), text.sections],
    [compact(kb.chunks, t), text.passages],
    [compact(kb.targets, t), text.targets],
    [compact(kb.conformers, t), text.conformers],
    [compact(kb.complexes, t), text.complexes],
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
          {text.title}
        </h2>
        {labelUpdate.can_start && (
          <button
            type="button"
            onClick={update}
            disabled={labelUpdate.running}
            className="rounded-md border border-rule px-2.5 py-1 text-xs text-ink-2 hover:text-foreground disabled:opacity-60 disabled:hover:text-ink-2"
          >
            {labelUpdate.running ? text.updating : text.updateNow}
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
          {kb.labels_fetched_to
            ? text.labelsFetched(longDate(kb.labels_fetched_to, t))
            : text.labelsNotFetched}
        </li>
        {labelUpdate.running ? (
          <li role="status">{text.updatingLabels}</li>
        ) : (
          last && <li>{text.lastUpdate(longDate(last.finished_at, t), updateResult(last, t))}</li>
        )}
        <li>{text.schema(kb.schema_version)}</li>
      </ul>
      {problem && (
        <p role="alert" className="mt-1.5 text-xs text-red-700 dark:text-red-400">
          {text.startFailed}
        </p>
      )}
    </section>
  );
}

function updateResult(run: NonNullable<LabelUpdateStatus["last_run"]>, t: Messages): string {
  const text = t.dashboard.knowledgeBase;
  const drugs = text.drugsChanged(run.drugs_changed);
  switch (run.outcome) {
    case "complete":
      return run.drugs_changed ? drugs : text.noLabelChanged;
    case "nothing_new":
      return text.nothingNew;
    case "incomplete":
      return text.incomplete(drugs);
    case "failed":
      return text.updateFailed;
  }
}
