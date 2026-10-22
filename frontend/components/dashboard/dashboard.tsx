"use client";

import { useEffect, useState } from "react";

import {
  ApiError,
  type ChatModel,
  type Stats,
  getChatModel,
  getStats,
  startLabelUpdate,
} from "@/lib/api";
import type { ChatHistory } from "@/lib/chat-history";
import { type Messages, useMessages } from "@/lib/messages";
import {
  OUTCOMES,
  RANGES,
  compact,
  count,
  percent,
  seconds,
  typicalWaitMs,
  usageTotals,
  usd,
} from "@/lib/stats";
import { useFetched } from "@/lib/use-fetched";
import { cn } from "cn";

import { ChatDrawer, ChatSidebar } from "../chat-sidebar";
import { Disclaimer } from "../disclaimer";
import { useSavedChats } from "../saved-chats";
import { type DaySeries, DayChart } from "./day-chart";
import { Errors, GuardSorting, KnowledgeBase, ToolCalls } from "./usage-cards";

type LoadState =
  { kind: "loading" } | { kind: "failed" } | { kind: "loaded"; stats: Stats; days: number };

// How often the page asks whether a label update has ended; re-embedding on a CPU takes minutes.
const UPDATE_POLL_MS = 5000;

const OUTCOME_COLOURS = {
  answered: {
    fill: "fill-outcome-answered",
    stroke: "stroke-outcome-answered",
    bg: "bg-outcome-answered",
  },
  stopped: {
    fill: "fill-outcome-stopped",
    stroke: "stroke-outcome-stopped",
    bg: "bg-outcome-stopped",
  },
  limited: {
    fill: "fill-outcome-limited",
    stroke: "stroke-outcome-limited",
    bg: "bg-outcome-limited",
  },
  error: { fill: "fill-outcome-error", stroke: "stroke-outcome-error", bg: "bg-outcome-error" },
};

const STRONG = { fill: "fill-usage-strong", stroke: "stroke-usage-strong", bg: "bg-usage-strong" };
const LIGHT = { fill: "fill-usage-light", stroke: "stroke-usage-light", bg: "bg-usage-light" };

function outcomeSeries(t: Messages): DaySeries[] {
  return OUTCOMES.map((outcome) => ({
    label: t.dashboard.outcomes[outcome],
    value: (day) => day.outcomes[outcome] ?? 0,
    ...OUTCOME_COLOURS[outcome],
  }));
}

function latencySeries(t: Messages): DaySeries[] {
  return [
    { label: t.dashboard.charts.median, value: (day) => day.latency_p50_ms, ...STRONG },
    { label: t.dashboard.charts.slowest, value: (day) => day.latency_p95_ms, ...LIGHT },
  ];
}

function tokenSeries(t: Messages): DaySeries[] {
  return [
    { label: t.dashboard.charts.input, value: (day) => day.input_tokens, ...STRONG },
    { label: t.dashboard.charts.output, value: (day) => day.output_tokens, ...LIGHT },
  ];
}

function costSeries(t: Messages): DaySeries[] {
  return [{ label: t.dashboard.charts.cost, value: (day) => day.cost_usd, ...STRONG }];
}

/** The dashboard page: what the store holds, then how the chat was used over the picked range. */
export function Dashboard({ history }: { history?: ChatHistory }) {
  const t = useMessages();
  const chats = useSavedChats(history);
  const [days, setDays] = useState<number>(30);
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [reloads, setReloads] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    getStats(days, controller.signal)
      .then((stats) => setState({ kind: "loaded", stats, days }))
      .catch(() => {
        if (!controller.signal.aborted) setState({ kind: "failed" });
      });
    return () => controller.abort();
  }, [days, reloads]);

  const updating = state.kind === "loaded" && state.stats.label_update.running;
  useEffect(() => {
    if (!updating) return;
    const timer = setTimeout(() => setReloads((n) => n + 1), UPDATE_POLL_MS);
    return () => clearTimeout(timer);
  }, [updating, state]);

  async function updateLabels() {
    try {
      const labelUpdate = await startLabelUpdate();
      setState((s) =>
        s.kind === "loaded" ? { ...s, stats: { ...s.stats, label_update: labelUpdate } } : s,
      );
    } catch (error) {
      // 409: a run started elsewhere, the nightly one perhaps; the reload shows it running.
      if (error instanceof ApiError && error.status === 409) setReloads((n) => n + 1);
      else throw error;
    }
  }

  const chatModel = useFetched(getChatModel, []);
  const model = chatModel.kind === "loaded" ? chatModel.value : null;

  return (
    <div className="flex flex-1">
      <ChatSidebar {...chats} />
      <main className="mx-auto flex w-full max-w-6xl min-w-0 flex-1 flex-col gap-4 px-4 py-8 sm:px-6 sm:py-12">
        <ChatDrawer {...chats} />
        <div className="mb-2 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">{t.dashboard.title}</h1>
            <p className="mt-1 text-sm text-ink-2">{t.dashboard.intro}</p>
          </div>
          <RangePicker days={days} onPick={setDays} />
        </div>
        {state.kind === "loading" && (
          <p role="status" className="text-sm text-ink-2">
            {t.dashboard.loading}
          </p>
        )}
        {state.kind === "failed" && (
          <p role="alert" className="text-sm text-red-700 dark:text-red-400">
            {t.dashboard.failed}
          </p>
        )}
        {state.kind === "loaded" && (
          // A new range keeps the old numbers, dimmed, until its own arrive.
          <div
            aria-busy={state.days !== days}
            className={cn(
              "flex flex-col gap-4 transition-opacity",
              state.days !== days && "opacity-60",
            )}
          >
            <KnowledgeBase
              kb={state.stats.knowledge_base}
              labelUpdate={state.stats.label_update}
              onUpdate={updateLabels}
            />
            <Usage usage={state.stats.usage} days={state.days} model={model} />
          </div>
        )}
        <footer className="mt-auto border-t border-rule pt-6">
          <Disclaimer />
        </footer>
      </main>
    </div>
  );
}

function RangePicker({ days, onPick }: { days: number; onPick: (days: number) => void }) {
  const t = useMessages();
  return (
    <div
      role="group"
      aria-label={t.dashboard.range}
      className="inline-flex overflow-hidden rounded-lg border border-input bg-card text-sm"
    >
      {RANGES.map((n) => (
        <button
          key={n}
          type="button"
          aria-pressed={n === days}
          onClick={() => onPick(n)}
          className={cn(
            "border-rule px-3 py-1.5 text-ink-2 not-first:border-l hover:text-foreground",
            n === days && "bg-ink text-card hover:text-card",
          )}
        >
          {t.dashboard.rangeOption(n)}
        </button>
      ))}
    </div>
  );
}

function Usage({
  usage,
  days,
  model,
}: {
  usage: Stats["usage"];
  days: number;
  model: ChatModel | null;
}) {
  const t = useMessages();
  const totals = usageTotals(usage.days);
  if (!totals.requests) {
    return (
      <div className="rounded-xl border border-dashed border-rule-2 bg-card px-4 py-10 text-center text-sm text-ink-2">
        <p className="mb-1 text-base font-semibold text-foreground">
          {t.dashboard.noRequests(days)}
        </p>
        {t.dashboard.noRequestsHint}
      </div>
    );
  }
  const hasCost = totals.costUsd > 0;
  const charts = t.dashboard.charts;
  const asCount = (n: number) => compact(n, t);
  return (
    <>
      <UsageNumbers totals={totals} wait={typicalWaitMs(usage.days)} days={days} model={model} />
      <div className="grid gap-4 lg:grid-cols-2">
        <DayChart
          title={charts.requestsPerDay}
          days={usage.days}
          series={outcomeSeries(t)}
          kind="columns"
          format={asCount}
        />
        <DayChart
          title={charts.timeToAnswer}
          days={usage.days}
          series={latencySeries(t)}
          kind="lines"
          format={(ms) => seconds(ms, t)}
          note={charts.answeredOnly}
        />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <ToolCalls counts={usage.tool_calls} />
        <GuardSorting counts={usage.categories} />
        <Errors counts={usage.errors} />
      </div>
      <div className={cn("grid gap-4", hasCost && "lg:grid-cols-2")}>
        <DayChart
          title={charts.tokensPerDay}
          days={usage.days}
          series={tokenSeries(t)}
          kind="columns"
          format={asCount}
        />
        {hasCost && (
          <DayChart
            title={charts.costPerDay}
            days={usage.days}
            series={costSeries(t)}
            kind="columns"
            format={(n) => usd(n, t)}
          />
        )}
      </div>
    </>
  );
}

function UsageNumbers({
  totals,
  wait,
  days,
  model,
}: {
  totals: ReturnType<typeof usageTotals>;
  wait: number | null;
  days: number;
  model: ChatModel | null;
}) {
  const t = useMessages();
  const text = t.dashboard.numbers;
  const numbers: [string, string, string][] = [
    [text.requests, count(totals.requests, t), text.lastRange(days)],
    [
      text.answered,
      percent(totals.answered / totals.requests, t),
      text.answeredOf(count(totals.answered, t), count(totals.requests, t)),
    ],
    [text.typicalWait, seconds(wait, t), text.medianAnswerTime],
    [
      text.tokens,
      compact(totals.inputTokens + totals.outputTokens, t),
      text.tokensInOut(compact(totals.inputTokens, t), compact(totals.outputTokens, t)),
    ],
    [text.cost, usd(totals.costUsd, t), costNote(totals.costUsd, model, t)],
  ];
  return (
    <dl className="grid grid-cols-2 overflow-hidden rounded-xl border border-rule bg-card sm:grid-cols-5">
      {numbers.map(([label, value, note], i) => (
        <div
          key={label}
          className={cn(
            "min-w-0 border-rule px-4 py-3.5",
            i % 2 === 1 && "max-sm:border-l",
            i >= 2 && "max-sm:border-t",
            i > 0 && "sm:border-l",
            i === 4 && "max-sm:col-span-2",
          )}
        >
          <dt className="text-xs text-ink-2">{label}</dt>
          <dd className="text-2xl font-semibold tracking-tight">{value}</dd>
          <dd className="text-xs text-ink-3">{note}</dd>
        </div>
      ))}
    </dl>
  );
}

function costNote(costUsd: number, model: ChatModel | null, t: Messages): string {
  if (costUsd > 0) return t.dashboard.numbers.costReported;
  if (model?.local) return t.dashboard.numbers.costFree;
  return t.dashboard.numbers.costNone;
}
