import type { ErrorKind, InputCategory, Outcome, Stats, UsageDay } from "./api";

export type Usage = Stats["usage"];

/** The `?days=` ranges the dashboard offers. */
export const RANGES = [7, 30, 90, 365] as const;

export const OUTCOMES: { key: Outcome; label: string }[] = [
  { key: "answered", label: "Answered" },
  { key: "stopped", label: "Stopped by the user" },
  { key: "limited", label: "Turned away by a limit" },
  { key: "error", label: "Error" },
];

export const CATEGORY_LABELS: Record<InputCategory, string> = {
  ok: "Medicine question",
  off_topic: "Off topic",
  personal_medical_advice: "Personal advice",
  overdose_emergency: "Overdose emergency",
  lethal_dose: "Lethal dose",
  synthesis_or_misuse: "Synthesis or misuse",
  prompt_injection: "Prompt injection",
};

export const ERROR_LABELS: Record<ErrorKind, string> = {
  timeout: "Timed out",
  model_error: "Model error",
  no_answer: "No answer",
  input_check_failed: "Input check failed",
  server_error: "Server error",
};

const sum = (values: number[]) => values.reduce((a, b) => a + b, 0);

export function usageTotals(days: UsageDay[]) {
  return {
    requests: sum(days.map((d) => d.requests)),
    answered: sum(days.map((d) => d.outcomes.answered ?? 0)),
    inputTokens: sum(days.map((d) => d.input_tokens)),
    outputTokens: sum(days.map((d) => d.output_tokens)),
    costUsd: sum(days.map((d) => d.cost_usd)),
  };
}

/** The median of the daily median latencies, over the days with an answer; null without one. */
export function typicalWaitMs(days: UsageDay[]): number | null {
  const medians = days
    .map((d) => d.latency_p50_ms)
    .filter((ms): ms is number => ms !== null)
    .sort((a, b) => a - b);
  if (!medians.length) return null;
  const middle = Math.floor(medians.length / 2);
  return medians.length % 2
    ? medians[middle]
    : Math.round((medians[middle - 1] + medians[middle]) / 2);
}

/** Counts sorted from most to least, without zeros. */
export function ranked<K extends string>(counts: Partial<Record<K, number>>): [K, number][] {
  return (Object.entries(counts) as [K, number][])
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1]);
}

/** 1,284 below ten thousand, then 12K and 5.5M. */
export function compact(n: number): string {
  if (n >= 1e6) return `${trim(n / 1e6)}M`;
  if (n >= 1e4) return `${Math.round(n / 1e3)}K`;
  return n.toLocaleString("en-GB");
}

function trim(n: number): string {
  return n.toFixed(1).replace(/\.0$/, "");
}

export function seconds(ms: number | null): string {
  return ms === null ? "–" : `${(ms / 1000).toFixed(1)} s`;
}

export function usd(n: number): string {
  return `$${n.toFixed(2)}`;
}

/** "21 Oct" for a `YYYY-MM-DD` UTC day. */
export function shortDate(day: string): string {
  return new Date(`${day}T00:00:00Z`).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
}

/** "12 Oct 2026" for a timestamp. */
export function longDate(timestamp: string): string {
  return new Date(timestamp).toLocaleDateString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}
