"use client";

import { type ReactNode, useState } from "react";

import type { UsageDay } from "@/lib/api";
import { shortDate } from "@/lib/stats";
import { useElementWidth } from "@/lib/use-element-width";
import { cn } from "cn";

import { FloatingTip, type TipAt } from "../benchmarks/floating-tip";

/** One measure per day. The colour classes are written out whole so Tailwind finds them. */
export type DaySeries = {
  label: string;
  value: (day: UsageDay) => number | null;
  fill: string;
  stroke: string;
  bg: string;
};

type DayChartProps = {
  title: string;
  days: UsageDay[];
  series: DaySeries[];
  kind: "columns" | "lines";
  format: (value: number) => string;
  note?: ReactNode;
};

const HEIGHT = 160;
const MARGIN = { left: 44, right: 8, top: 8, bottom: 22 };

/** A rounded axis top: 1, 2, 2.5 or 5 times a power of ten. */
function niceMax(value: number): number {
  if (value <= 0) return 1;
  const power = 10 ** Math.floor(Math.log10(value));
  return [1, 2, 2.5, 5, 10].map((m) => m * power).find((m) => m >= value) ?? 10 * power;
}

/** A chart card for a measure over the days of the range, columns stacked per day or lines, with a
 * tooltip per day and a table of the same numbers behind a button. */
export function DayChart({ title, days, series, kind, format, note }: DayChartProps) {
  const [asTable, setAsTable] = useState(false);
  return (
    <section className="min-w-0 rounded-xl border border-rule bg-card p-4">
      <div className="mb-2 flex items-baseline justify-between gap-3">
        <h2 className="text-sm font-semibold text-ink-2">{title}</h2>
        <button
          type="button"
          onClick={() => setAsTable(!asTable)}
          className="text-xs text-ink-3 underline-offset-4 hover:text-foreground hover:underline"
        >
          {asTable ? "Show chart" : "Show table"}
        </button>
      </div>
      {series.length > 1 && <Legend series={series} line={kind === "lines"} />}
      {asTable ? (
        <DayTable days={days} series={series} format={format} />
      ) : (
        <DayPlot title={title} days={days} series={series} kind={kind} format={format} />
      )}
      {note && <p className="mt-1.5 text-xs text-ink-3">{note}</p>}
    </section>
  );
}

function Legend({ series, line }: { series: DaySeries[]; line: boolean }) {
  return (
    <div className="mb-1.5 flex flex-wrap gap-x-3 gap-y-1 text-xs text-ink-2">
      {series.map((s) => (
        <span key={s.label} className="inline-flex items-center gap-1.5">
          <i className={cn(line ? "h-0.5 w-3.5 rounded-full" : "size-2.5 rounded-[3px]", s.bg)} />
          {s.label}
        </span>
      ))}
    </div>
  );
}

function DayPlot({ title, days, series, kind, format }: Omit<DayChartProps, "note">) {
  const [ref, width] = useElementWidth();
  const [hover, setHover] = useState<(TipAt & { i: number }) | null>(null);
  const plotWidth = width - MARGIN.left - MARGIN.right;
  const plotHeight = HEIGHT - MARGIN.top - MARGIN.bottom;
  const slot = plotWidth / days.length;
  const values = days.map((day) => series.map((s) => s.value(day)));
  const top = niceMax(
    Math.max(
      ...values.map((row) =>
        kind === "columns"
          ? row.reduce<number>((a, v) => a + (v ?? 0), 0)
          : Math.max(0, ...row.map((v) => v ?? 0)),
      ),
    ),
  );
  const x = (i: number) => MARGIN.left + (i + 0.5) * slot;
  const y = (value: number) => MARGIN.top + (1 - value / top) * plotHeight;
  // Dates are labelled back from today, so the newest day always has one.
  const labelEvery = Math.ceil(days.length / Math.max(2, Math.floor(plotWidth / 72)));

  return (
    <div ref={ref} className="relative w-full">
      <svg
        width={width}
        height={HEIGHT}
        role="img"
        aria-label={`${title}, ${days.length} days; the table has the numbers`}
        className="block overflow-visible text-[11px] [&_text]:fill-ink-3"
        onPointerMove={(e) => {
          const left = e.currentTarget.getBoundingClientRect().left;
          const i = Math.floor((e.clientX - left - MARGIN.left) / slot);
          setHover({ x: e.clientX, y: e.clientY, i: Math.min(days.length - 1, Math.max(0, i)) });
        }}
        onPointerLeave={() => setHover(null)}
      >
        {hover && (
          <rect
            x={MARGIN.left + hover.i * slot}
            y={MARGIN.top}
            width={slot}
            height={plotHeight}
            className="fill-rule/60"
          />
        )}
        {[0, 0.5, 1].map((share) => (
          <g key={share}>
            <line
              x1={MARGIN.left}
              x2={MARGIN.left + plotWidth}
              y1={y(top * share)}
              y2={y(top * share)}
              className={share ? "stroke-rule" : "stroke-rule-2"}
            />
            <text
              x={MARGIN.left - 6}
              y={y(top * share) + 4}
              textAnchor="end"
              className="tabular-nums"
            >
              {format(top * share)}
            </text>
          </g>
        ))}
        {days.map((day, i) =>
          (days.length - 1 - i) % labelEvery === 0 ? (
            <text key={day.date} x={x(i)} y={HEIGHT - 6} textAnchor="middle">
              {shortDate(day.date)}
            </text>
          ) : null,
        )}
        {kind === "columns" ? (
          <Columns values={values} series={series} slot={slot} x={x} y={y} />
        ) : (
          <Lines values={values} series={series} x={x} y={y} />
        )}
      </svg>
      {hover && (
        <FloatingTip at={hover}>
          <div className="mb-1 font-semibold">{shortDate(days[hover.i].date)}</div>
          {series.map((s, j) => (
            <div key={s.label} className="flex items-center gap-1.5">
              <span className={cn("size-2 rounded-[2px]", s.bg)} />
              <b className="tabular-nums">
                {values[hover.i][j] === null ? "–" : format(values[hover.i][j]!)}
              </b>
              {s.label}
            </div>
          ))}
        </FloatingTip>
      )}
    </div>
  );
}

type Values = (number | null)[][];

/** Stacked columns at most 24 px wide, with a 2 px gap between the parts and a rounded top. */
function Columns({
  values,
  series,
  slot,
  x,
  y,
}: {
  values: Values;
  series: DaySeries[];
  slot: number;
  x: (i: number) => number;
  y: (value: number) => number;
}) {
  const gap = slot > 6 ? 2 : 0;
  const width = Math.max(1, Math.min(24, slot - gap));
  return values.map((row, i) => {
    let base = 0;
    const parts = row.flatMap((value, j) => {
      if (!value) return [];
      const part = { j, from: base, to: base + value };
      base += value;
      return [part];
    });
    return parts.map(({ j, from, to }, k) => {
      const bottom = y(from) - (k > 0 ? gap : 0);
      const height = Math.max(0, bottom - y(to));
      const radius = k === parts.length - 1 ? Math.min(4, width / 2, height) : 0;
      const left = x(i) - width / 2;
      return (
        <path
          key={`${i}-${j}`}
          d={`M${left},${bottom}v${-(height - radius)}q0,${-radius} ${radius},${-radius}h${width - 2 * radius}q${radius},0 ${radius},${radius}v${height - radius}z`}
          className={series[j].fill}
        />
      );
    });
  });
}

/** 2 px lines that break on a day without a value; a day standing alone gets a dot. */
function Lines({
  values,
  series,
  x,
  y,
}: {
  values: Values;
  series: DaySeries[];
  x: (i: number) => number;
  y: (value: number) => number;
}) {
  return [...series.keys()].reverse().map((j) => {
    const at = (i: number) => values[i]?.[j] ?? null;
    const path = values
      .map((_, i) => {
        const value = at(i);
        if (value === null) return "";
        return `${at(i - 1) === null ? "M" : "L"}${x(i).toFixed(1)},${y(value).toFixed(1)}`;
      })
      .join("");
    const alone = values.flatMap((_, i) =>
      at(i) !== null && at(i - 1) === null && at(i + 1) === null ? [i] : [],
    );
    return (
      <g key={series[j].label}>
        <path
          d={path}
          fill="none"
          strokeWidth={2}
          strokeLinejoin="round"
          strokeLinecap="round"
          className={series[j].stroke}
        />
        {alone.map((i) => (
          <circle
            key={i}
            cx={x(i)}
            cy={y(at(i)!)}
            r={4}
            strokeWidth={2}
            className={cn(series[j].fill, "stroke-card")}
          />
        ))}
      </g>
    );
  });
}

/** The chart's numbers, one row per day with a request. */
function DayTable({
  days,
  series,
  format,
}: {
  days: UsageDay[];
  series: DaySeries[];
  format: (value: number) => string;
}) {
  const rows = days.filter((day) => day.requests > 0).reverse();
  return (
    <div className="max-h-64 overflow-y-auto">
      <table className="w-full text-xs tabular-nums">
        <thead className="sticky top-0 bg-card text-ink-3">
          <tr>
            <th className="py-1 text-left font-medium">Day</th>
            {series.map((s) => (
              <th key={s.label} className="py-1 pl-3 text-right font-medium">
                {s.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((day) => (
            <tr key={day.date} className="border-t border-rule">
              <td className="py-1">{shortDate(day.date)}</td>
              {series.map((s) => {
                const value = s.value(day);
                return (
                  <td key={s.label} className="py-1 pl-3 text-right">
                    {value === null ? "–" : format(value)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-1.5 text-xs text-ink-3">Days without a request are left out.</p>
    </div>
  );
}
