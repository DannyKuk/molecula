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
import { OUTCOMES, RANGES, compact, seconds, typicalWaitMs, usageTotals, usd } from "@/lib/stats";
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

const OUTCOME_SERIES: DaySeries[] = OUTCOMES.map(({ key, label }) => ({
  label,
  value: (day) => day.outcomes[key] ?? 0,
  ...{
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
  }[key],
}));

const STRONG = { fill: "fill-usage-strong", stroke: "stroke-usage-strong", bg: "bg-usage-strong" };
const LIGHT = { fill: "fill-usage-light", stroke: "stroke-usage-light", bg: "bg-usage-light" };

const LATENCY_SERIES: DaySeries[] = [
  { label: "Median (p50)", value: (day) => day.latency_p50_ms, ...STRONG },
  { label: "Slowest 5% (p95)", value: (day) => day.latency_p95_ms, ...LIGHT },
];

const TOKEN_SERIES: DaySeries[] = [
  { label: "Read by the model (input)", value: (day) => day.input_tokens, ...STRONG },
  { label: "Written (output)", value: (day) => day.output_tokens, ...LIGHT },
];

const COST_SERIES: DaySeries[] = [{ label: "Cost", value: (day) => day.cost_usd, ...STRONG }];

/** The dashboard page: what the store holds, then how the chat was used over the picked range. */
export function Dashboard({ history }: { history?: ChatHistory }) {
  const chats = useSavedChats(history);
  const [days, setDays] = useState<number>(30);
  const [state, setState] = useState<LoadState>({ kind: "loading" });
  const [model, setModel] = useState<ChatModel | null>(null);
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

  useEffect(() => {
    const controller = new AbortController();
    getChatModel(controller.signal)
      .then(setModel)
      .catch(() => {});
    return () => controller.abort();
  }, []);

  return (
    <div className="flex flex-1">
      <ChatSidebar {...chats} />
      <main className="mx-auto flex w-full max-w-6xl min-w-0 flex-1 flex-col gap-4 px-4 py-8 sm:px-6 sm:py-12">
        <ChatDrawer {...chats} />
        <div className="mb-2 flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
            <p className="mt-1 text-sm text-ink-2">
              What Molecula answers from, and how the chat is used.
            </p>
          </div>
          <RangePicker days={days} onPick={setDays} />
        </div>
        {state.kind === "loading" && (
          <p role="status" className="text-sm text-ink-2">
            Loading the numbers…
          </p>
        )}
        {state.kind === "failed" && (
          <p role="alert" className="text-sm text-red-700 dark:text-red-400">
            Could not load the numbers. Check that the backend is running, then reload the page.
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
  return (
    <div
      role="group"
      aria-label="Range"
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
          {n === 365 ? "1 year" : `${n} days`}
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
  const totals = usageTotals(usage.days);
  if (!totals.requests) {
    return (
      <div className="rounded-xl border border-dashed border-rule-2 bg-card px-4 py-10 text-center text-sm text-ink-2">
        <p className="mb-1 text-base font-semibold text-foreground">
          No chat requests in the last {days} days
        </p>
        Ask something in the chat and it shows up here.
      </div>
    );
  }
  const hasCost = totals.costUsd > 0;
  return (
    <>
      <UsageNumbers totals={totals} wait={typicalWaitMs(usage.days)} days={days} model={model} />
      <div className="grid gap-4 lg:grid-cols-2">
        <DayChart
          title="Requests per day"
          days={usage.days}
          series={OUTCOME_SERIES}
          kind="columns"
          format={compact}
        />
        <DayChart
          title="Time to answer"
          days={usage.days}
          series={LATENCY_SERIES}
          kind="lines"
          format={seconds}
          note="Answered requests only."
        />
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <ToolCalls counts={usage.tool_calls} />
        <GuardSorting counts={usage.categories} />
        <Errors counts={usage.errors} />
      </div>
      <div className={cn("grid gap-4", hasCost && "lg:grid-cols-2")}>
        <DayChart
          title="Tokens per day"
          days={usage.days}
          series={TOKEN_SERIES}
          kind="columns"
          format={compact}
        />
        {hasCost && (
          <DayChart
            title="Cost per day"
            days={usage.days}
            series={COST_SERIES}
            kind="columns"
            format={usd}
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
  const numbers: [string, string, string][] = [
    [
      "Requests",
      totals.requests.toLocaleString("en-GB"),
      `last ${days === 365 ? "year" : `${days} days`}`,
    ],
    [
      "Answered",
      `${Math.round((totals.answered / totals.requests) * 100)}%`,
      `${totals.answered.toLocaleString("en-GB")} of ${totals.requests.toLocaleString("en-GB")}`,
    ],
    ["Typical wait", seconds(wait), "median answer time"],
    [
      "Tokens",
      compact(totals.inputTokens + totals.outputTokens),
      `${compact(totals.inputTokens)} in · ${compact(totals.outputTokens)} out`,
    ],
    ["Cost", usd(totals.costUsd), costNote(totals.costUsd, model)],
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

function costNote(costUsd: number, model: ChatModel | null): string {
  if (costUsd > 0) return "reported by the cloud model";
  if (model?.local) return "local model, tokens are free";
  return "none reported";
}
