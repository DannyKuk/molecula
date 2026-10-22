import {
  type Benchmark,
  type Model,
  type Rank,
  type Scope,
  GROUP_NAMES,
  formatSize,
  isHit,
  ordinal,
  percent,
} from "@/lib/embedding-benchmark";

import { AppBadge, Pill } from "./question-view";
import { ModelRecall } from "./recall-chart";

function missedRank(rank: Rank): string {
  return rank === null ? "not in 10" : ordinal(rank);
}

export function cpuTime(model: Model): { value: string; note?: string } {
  if (model.cpu_query_ms !== null) return { value: `${model.cpu_query_ms} ms` };
  return {
    value: "—",
    note:
      model.group === "cloud"
        ? `cloud, ${model.query_ms} ms`
        : `needs a GPU (${model.query_ms} ms there)`,
  };
}

/** One model: its recall curves, its costs and the questions it missed in the top 5. */
export function ModelView({
  benchmark,
  model,
  scope,
  onQuestion,
}: {
  benchmark: Benchmark;
  model: Model;
  scope: Scope;
  onQuestion: (question: number) => void;
}) {
  const ranks = benchmark.ranks[model.label][scope];
  const missed = benchmark.sections
    .flatMap((s) => s.questions)
    .filter((q) => !isHit(ranks[q.index]));
  const cpu = cpuTime(model);
  const facts: [string, string][] = [
    ["Answer in top 5, within the drug", percent(model.recall_at_5.in_drug)],
    ["… over the whole index", percent(model.recall_at_5.whole_index)],
    ["Time per question on a CPU", cpu.note ? `${cpu.value} (${cpu.note})` : cpu.value],
    ["Index size", formatSize(model.index_mb)],
    [
      "Model download",
      model.weights_mb === null ? "— (runs in the cloud)" : formatSize(model.weights_mb),
    ],
  ];

  return (
    <div className="flex flex-col gap-3.5">
      <div className="flex flex-wrap items-center gap-1.5">
        <Pill>{GROUP_NAMES[model.group]}</Pill>
        {model.isApp && <AppBadge />}
      </div>
      <div>
        <p className="text-lg font-semibold tracking-tight">{model.name}</p>
        <p className="text-xs text-ink-2">{model.model}</p>
      </div>
      <ModelRecall benchmark={benchmark} model={model} height={180} detailed />
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-[0.8125rem]">
        {facts.map(([term, value]) => (
          <div key={term} className="contents">
            <dt className="text-ink-2">{term}</dt>
            <dd className="tabular-nums">{value}</dd>
          </div>
        ))}
      </dl>
      <h3 className="font-semibold">Missed in the top 5 ({missed.length})</h3>
      <ul className="flex flex-col">
        {missed.map((q) => (
          <li key={q.index}>
            <button
              type="button"
              onClick={() => onQuestion(q.index)}
              className="flex w-full justify-between gap-2 border-l-2 border-rule-2 py-1.5 pr-1 pl-3 text-left text-[0.8125rem] hover:border-ink-3 hover:bg-panel"
            >
              <span>{q.question}</span>
              <span className="whitespace-nowrap text-ink-3 tabular-nums">
                {missedRank(ranks[q.index])}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
