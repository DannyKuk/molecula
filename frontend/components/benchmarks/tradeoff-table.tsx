import { cn } from "cn";
import { Fragment } from "react";

import { type Benchmark, GROUP_NAMES, formatSize, percent } from "@/lib/embedding-benchmark";

import { cpuTime } from "./model-view";
import { AppBadge } from "./question-view";

const COLUMNS = [
  "Answer in top 5, within the drug",
  "… over the whole index",
  "Time per question on a CPU",
  "Index size",
  "Model download",
];

const APP_ROW = "bg-signal-tint";

function Note({ children }: { children: React.ReactNode }) {
  return <span className="block text-[0.72rem] font-normal text-ink-3">{children}</span>;
}

/** Recall@5 against what each model costs: CPU time per question, index size, download size. */
export function TradeoffTable({ benchmark }: { benchmark: Benchmark }) {
  const groups = [...new Set(benchmark.models.map((m) => m.group))];
  const cell = "border-b px-2.5 py-2 text-right whitespace-nowrap tabular-nums";

  return (
    <div className="max-w-full overflow-x-auto">
      <table className="w-full border-collapse text-sm">
        <thead>
          <tr className="text-xs text-ink-2">
            <th className="sticky left-0 border-b bg-background px-2.5 py-2 text-left align-bottom font-medium">
              Model
            </th>
            {COLUMNS.map((column) => (
              <th
                key={column}
                className="min-w-24 border-b px-2.5 py-2 text-right align-bottom font-medium"
              >
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {groups.map((group) => (
            <Fragment key={group}>
              <tr>
                <td
                  colSpan={COLUMNS.length + 1}
                  className="border-b border-rule-2 px-2.5 pt-4 pb-2 text-xs font-semibold text-ink-2"
                >
                  {GROUP_NAMES[group]}
                </td>
              </tr>
              {benchmark.models
                .filter((m) => m.group === group)
                .map((m) => {
                  const cpu = cpuTime(m);
                  const recall = m.recall_at_5.in_drug;
                  return (
                    <tr key={m.label} className={cn(m.isApp && APP_ROW)}>
                      <td
                        className={cn(
                          "sticky left-0 border-b px-2.5 py-2 whitespace-nowrap",
                          m.isApp ? APP_ROW : "bg-background",
                        )}
                      >
                        <span className={cn(m.isApp && "flex flex-wrap items-center gap-x-2")}>
                          {m.name}
                          {m.isApp && <AppBadge />}
                        </span>
                      </td>
                      <td className={cell}>
                        <span className="inline-flex items-center gap-2">
                          <span
                            style={{ width: Math.max(2, Math.round(((recall - 0.7) / 0.3) * 64)) }}
                            className={cn(
                              "h-2 rounded-r",
                              m.isApp ? "bg-series-drug" : "bg-rule-2",
                            )}
                          />
                          {percent(recall)}
                        </span>
                      </td>
                      <td className={cell}>{percent(m.recall_at_5.whole_index)}</td>
                      <td className={cell}>
                        {cpu.value}
                        {cpu.note && <Note>{cpu.note}</Note>}
                      </td>
                      <td className={cell}>{formatSize(m.index_mb)}</td>
                      <td className={cell}>
                        {formatSize(m.weights_mb)}
                        {m.weights_mb === null && <Note>runs in the cloud</Note>}
                      </td>
                    </tr>
                  );
                })}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  );
}
