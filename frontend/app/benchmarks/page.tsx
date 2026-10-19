import type { Metadata } from "next";

import { Benchmarks } from "@/components/benchmarks/benchmarks";
import { Disclaimer } from "@/components/disclaimer";

export const metadata: Metadata = {
  title: "Benchmarks · Molecula",
  description:
    "How Molecula's retrieval was chosen: the embedding models compared, question by question.",
};

export default function BenchmarksPage() {
  return (
    <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col gap-6 px-4 py-8 sm:px-6 sm:py-12">
      <Benchmarks />
      <footer className="mt-auto border-t border-zinc-200 pt-6 dark:border-zinc-800">
        <Disclaimer />
      </footer>
    </main>
  );
}
