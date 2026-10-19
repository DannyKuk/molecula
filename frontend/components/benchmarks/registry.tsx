import type { ReactNode } from "react";

import embeddingRun from "@/lib/benchmarks/embeddings-2026-10-12.json";
import type { EmbeddingRun } from "@/lib/embedding-benchmark";

import { EmbeddingBenchmark } from "./embedding-benchmark";

export type BenchmarkEntry = { id: string; title: string; render: () => ReactNode };

/** The benchmarks the page can show, newest first. A new one (the RAGAs evaluation #43, the safety
 * eval #17) is one more entry with its committed results file and its components. */
export const BENCHMARKS: BenchmarkEntry[] = [
  {
    id: "embeddings-2026-10-12",
    title: "Embedding models · 12 Oct 2026",
    render: () => <EmbeddingBenchmark run={embeddingRun as EmbeddingRun} />,
  },
];
