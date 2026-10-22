import type { ReactNode } from "react";

import chatModelRun from "@/lib/benchmarks/chat-models-2026-10-22.json";
import embeddingRun from "@/lib/benchmarks/embeddings-2026-10-12.json";
import type { ChatModelRun } from "@/lib/chat-model-benchmark";
import type { EmbeddingRun } from "@/lib/embedding-benchmark";

import { ChatModelBenchmark } from "./chat-model-benchmark";
import { EmbeddingBenchmark } from "./embedding-benchmark";

export type BenchmarkEntry = { id: string; title: string; render: () => ReactNode };

/** The benchmarks the page can show, newest first. A new one is one more entry with its committed
 * results file and its components. */
export const BENCHMARKS: BenchmarkEntry[] = [
  {
    id: "chat-models-2026-10-22",
    title: "Chat models · 22 Oct 2026",
    render: () => <ChatModelBenchmark run={chatModelRun as ChatModelRun} />,
  },
  {
    id: "embeddings-2026-10-12",
    title: "Embedding models · 12 Oct 2026",
    render: () => <EmbeddingBenchmark run={embeddingRun as EmbeddingRun} />,
  },
];
