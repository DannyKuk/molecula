import type { Outcome, Stats, UsageDay } from "./api";
import { en, type Messages } from "./messages";

export type Usage = Stats["usage"];

/** The `?days=` ranges the dashboard offers. */
export const RANGES = [7, 30, 90, 365] as const;

/** The outcomes in the order the dashboard stacks and lists them. */
export const OUTCOMES: Outcome[] = ["answered", "stopped", "limited", "error"];

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

/** 1,284 below ten thousand, then 12K and 5.5M; in German 1.284, 12 Tsd. and 5,5 Mio. */
export function compact(n: number, t: Messages = en): string {
  if (n >= 1e6) return t.dashboard.millions(oneDecimal(n / 1e6, t, 0));
  if (n >= 1e4) return t.dashboard.thousands(count(Math.round(n / 1e3), t));
  return count(n, t);
}

export function count(n: number, t: Messages = en): string {
  return n.toLocaleString(t.locale);
}

export function percent(share: number, t: Messages = en): string {
  return share.toLocaleString(t.locale, { style: "percent" });
}

function oneDecimal(n: number, t: Messages, minimumFractionDigits: number): string {
  return n.toLocaleString(t.locale, { minimumFractionDigits, maximumFractionDigits: 1 });
}

export function seconds(ms: number | null, t: Messages = en): string {
  return ms === null ? "–" : `${oneDecimal(ms / 1000, t, 1)} s`;
}

export function usd(n: number, t: Messages = en): string {
  return n.toLocaleString(t.locale, { style: "currency", currency: "USD" });
}

/** "Oct 21" for a `YYYY-MM-DD` UTC day; "21. Okt." in German. */
export function shortDate(day: string, t: Messages = en): string {
  return new Date(`${day}T00:00:00Z`).toLocaleDateString(t.locale, {
    day: "numeric",
    month: "short",
    timeZone: "UTC",
  });
}

/** "Oct 12, 2026" for a timestamp; "12. Okt. 2026" in German. */
export function longDate(timestamp: string, t: Messages = en): string {
  return new Date(timestamp).toLocaleDateString(t.locale, {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  });
}
