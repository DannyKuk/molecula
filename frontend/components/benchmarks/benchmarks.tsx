"use client";

import Link from "next/link";
import { useState } from "react";

import { BENCHMARKS } from "./registry";

/** The benchmark page: a picker at the top, then the picked benchmark. */
export function Benchmarks() {
  const [id, setId] = useState(BENCHMARKS[0].id);
  const benchmark = BENCHMARKS.find((b) => b.id === id) ?? BENCHMARKS[0];

  return (
    <>
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
        <Link
          href="/"
          className="text-sm text-zinc-600 underline-offset-4 hover:underline dark:text-zinc-400"
        >
          ← Molecula
        </Link>
        <label className="inline-flex items-center gap-2 text-sm text-zinc-600 dark:text-zinc-400">
          Benchmark
          <select
            value={id}
            onChange={(e) => setId(e.target.value)}
            className="max-w-full rounded-lg border border-input bg-background px-2.5 py-1.5 text-foreground"
          >
            {BENCHMARKS.map((b) => (
              <option key={b.id} value={b.id}>
                {b.title}
              </option>
            ))}
          </select>
        </label>
      </div>
      {benchmark.render()}
    </>
  );
}
