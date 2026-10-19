import type { Metadata } from "next";

import { Benchmarks } from "@/components/benchmarks/benchmarks";

export const metadata: Metadata = {
  title: "Benchmarks · Molecula",
  description:
    "How Molecula's retrieval was chosen: the embedding models compared, question by question.",
};

export default function BenchmarksPage() {
  return <Benchmarks />;
}
