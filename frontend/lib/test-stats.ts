import type { Stats, UsageDay } from "./api";

function day(date: string, fields: Partial<UsageDay> = {}): UsageDay {
  return {
    date,
    requests: 0,
    outcomes: {},
    latency_p50_ms: null,
    latency_p95_ms: null,
    input_tokens: 0,
    output_tokens: 0,
    cost_usd: 0,
    ...fields,
  };
}

const KNOWLEDGE_BASE: Stats["knowledge_base"] = {
  drugs: 133,
  labels: 156,
  label_sections: 3126,
  chunks: 7012,
  targets: 189,
  conformers: 131,
  complexes: 73,
  schema_version: 6,
  labels_fetched_from: "2026-10-12T08:45:23Z",
  labels_fetched_to: "2026-10-12T08:45:29Z",
};

const NO_LABEL_UPDATE: Stats["label_update"] = { last_run: null, running: false, can_start: false };

/** Three days of a local model: 5 requests, 3 answered, one stopped, one timed out. */
export const STATS: Stats = {
  knowledge_base: KNOWLEDGE_BASE,
  label_update: NO_LABEL_UPDATE,
  usage: {
    days: [
      day("2026-10-19", {
        requests: 2,
        outcomes: { answered: 1, error: 1 },
        latency_p50_ms: 12000,
        latency_p95_ms: 12000,
        input_tokens: 9000,
        output_tokens: 500,
      }),
      day("2026-10-20"),
      day("2026-10-21", {
        requests: 3,
        outcomes: { answered: 2, stopped: 1 },
        latency_p50_ms: 14000,
        latency_p95_ms: 20000,
        input_tokens: 18000,
        output_tokens: 1100,
      }),
    ],
    tool_calls: { resolve_drug: 3, search_labels: 2 },
    categories: { ok: 3, off_topic: 1 },
    errors: { timeout: 1 },
  },
};

export const EMPTY_STATS: Stats = {
  knowledge_base: KNOWLEDGE_BASE,
  label_update: NO_LABEL_UPDATE,
  usage: {
    days: [day("2026-10-20"), day("2026-10-21")],
    tool_calls: {},
    categories: {},
    errors: {},
  },
};

/** The same use, on a cloud model that reported its cost. */
export const CLOUD_STATS: Stats = {
  ...STATS,
  usage: {
    ...STATS.usage,
    days: STATS.usage.days.map((d) => ({ ...d, cost_usd: d.requests ? 0.0125 : 0 })),
  },
};
