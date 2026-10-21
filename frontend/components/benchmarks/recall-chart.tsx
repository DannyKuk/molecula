"use client";

import { useState } from "react";

import {
  type Benchmark,
  type Model,
  type Scope,
  percent,
  recallCurve,
  recallFloor,
} from "@/lib/embedding-benchmark";
import { useElementWidth } from "@/lib/use-element-width";

import { FloatingTip, type TipAt } from "./floating-tip";

export const SERIES = [
  {
    key: "drug",
    label: "within the drug",
    stroke: "stroke-series-drug",
    fill: "fill-series-drug",
    bg: "bg-series-drug",
  },
  {
    key: "index",
    label: "whole index",
    stroke: "stroke-series-index",
    fill: "fill-series-index",
    bg: "bg-series-index",
  },
] as const;

type RecallChartProps = {
  name: string;
  drug: number[];
  index: number[];
  others: number[][];
  floor: number;
  height: number;
  detailed?: boolean;
};

/** One model's recall@k for k = 1–10, within the drug and over the whole index, with the other
 * models' within-drug curves faint behind it. */
function RecallChart({ name, drug, index, others, floor, height, detailed }: RecallChartProps) {
  const [ref, width] = useElementWidth();
  const [hover, setHover] = useState<(TipAt & { k: number }) | null>(null);
  const margin = { left: 36, right: 10, top: 10, bottom: detailed ? 30 : 20 };
  const plotWidth = width - margin.left - margin.right;
  const plotHeight = height - margin.top - margin.bottom;
  const x = (k: number) => margin.left + ((k - 1) / 9) * plotWidth;
  const y = (share: number) => margin.top + (1 - (share - floor) / (1 - floor)) * plotHeight;
  const path = (values: number[]) =>
    values.map((v, i) => `${i ? "L" : "M"}${x(i + 1).toFixed(1)},${y(v).toFixed(1)}`).join("");
  const yTicks = Array.from(
    { length: Math.round((1 - floor) / 0.2) + 1 },
    (_, i) => floor + i * 0.2,
  );
  const values = { drug, index };

  return (
    <div ref={ref} className="relative w-full">
      <svg
        width={width}
        height={height}
        role="img"
        aria-label={`${name}: answer in the top 5 for ${percent(drug[4])} within the drug, ${percent(index[4])} over the whole index`}
        className="block overflow-visible text-[11px] [&_text]:fill-ink-3"
        onPointerMove={(e) => {
          const left = e.currentTarget.getBoundingClientRect().left;
          const k = Math.round(((e.clientX - left - margin.left) / plotWidth) * 9 + 1);
          setHover({ x: e.clientX, y: e.clientY, k: Math.min(10, Math.max(1, k)) });
        }}
        onPointerLeave={() => setHover(null)}
      >
        {yTicks.map((tick) => (
          <g key={tick}>
            <line
              x1={margin.left}
              x2={margin.left + plotWidth}
              y1={y(tick)}
              y2={y(tick)}
              className="stroke-rule"
            />
            <text x={margin.left - 6} y={y(tick) + 4} textAnchor="end" className="tabular-nums">
              {percent(tick)}
            </text>
          </g>
        ))}
        <line
          x1={margin.left}
          x2={margin.left + plotWidth}
          y1={y(floor)}
          y2={y(floor)}
          className="stroke-rule-2"
        />
        {[1, 5, 10].map((k) => (
          <text key={k} x={x(k)} y={margin.top + plotHeight + 16} textAnchor="middle">
            {k}
          </text>
        ))}
        {detailed && (
          <>
            <text
              x={margin.left + plotWidth}
              y={height - 2}
              textAnchor="end"
              className="text-[10px]"
            >
              k = passages the model returns
            </text>
            <line
              x1={x(5)}
              x2={x(5)}
              y1={margin.top}
              y2={margin.top + plotHeight}
              strokeDasharray="3 3"
              className="stroke-ink-3"
            />
            <text x={x(5) + 4} y={margin.top + 10} className="text-[10px]">
              top 5
            </text>
          </>
        )}
        <g fill="none" strokeLinejoin="round" strokeLinecap="round">
          {others.map((curve, i) => (
            <path key={i} d={path(curve)} className="stroke-rule-2" />
          ))}
          {[...SERIES].reverse().map((s) => (
            <path key={s.key} d={path(values[s.key])} strokeWidth={2} className={s.stroke} />
          ))}
        </g>
        {hover && (
          <g>
            <line
              x1={x(hover.k)}
              x2={x(hover.k)}
              y1={margin.top}
              y2={margin.top + plotHeight}
              strokeDasharray="2 3"
              className="stroke-ink-3"
            />
            {SERIES.map((s) => (
              <circle
                key={s.key}
                cx={x(hover.k)}
                cy={y(values[s.key][hover.k - 1])}
                r={4}
                strokeWidth={2}
                className={`${s.fill} stroke-background`}
              />
            ))}
          </g>
        )}
      </svg>
      {hover && (
        <FloatingTip at={hover}>
          <div className="mb-1 font-semibold">
            {name}, answer in the top {hover.k}
          </div>
          {SERIES.map((s) => (
            <div key={s.key} className="flex items-center gap-1.5">
              <span className={`h-0.5 w-3 rounded-full ${s.bg}`} />
              <b className="min-w-[2.6em] tabular-nums">{percent(values[s.key][hover.k - 1])}</b>
              {s.label}
            </div>
          ))}
        </FloatingTip>
      )}
    </div>
  );
}

export function RecallLegend() {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1.5 text-[0.8125rem] text-ink-2">
      <span className="inline-flex items-center gap-1.5">
        <i className="h-0.5 w-4 rounded-full bg-series-drug" />
        Within the drug (what the app does)
      </span>
      <span className="inline-flex items-center gap-1.5">
        <i className="h-0.5 w-4 rounded-full bg-series-index" />
        Over the whole index
      </span>
      <span className="inline-flex items-center gap-1.5">
        <i className="h-0.5 w-4 rounded-full bg-rule-2" />
        The other models, within the drug
      </span>
    </div>
  );
}

export function ModelRecall({
  benchmark,
  model,
  height,
  detailed,
}: {
  benchmark: Benchmark;
  model: Model;
  height: number;
  detailed?: boolean;
}) {
  const curve = (label: string, scope: Scope) => recallCurve(benchmark.ranks[label][scope]);
  return (
    <RecallChart
      name={model.name}
      drug={curve(model.label, "in_drug")}
      index={curve(model.label, "whole_index")}
      others={benchmark.models.filter((o) => o !== model).map((o) => curve(o.label, "in_drug"))}
      floor={recallFloor(benchmark)}
      height={height}
      detailed={detailed}
    />
  );
}
