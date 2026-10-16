"use client";

import { Check, Copy } from "lucide-react";
import { useEffect, useState } from "react";

import type { Turn } from "@/lib/chat-turn";
import { checkReport } from "@/lib/check-report";

const SHOWN_MS = 2000;

/** Copies the turn's answer, tool results and source-check verdicts as one report (#221). */
export function CopyCheckReport({ turn }: { turn: Turn }) {
  const [copied, setCopied] = useState<"copied" | "failed" | null>(null);

  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(null), SHOWN_MS);
    return () => clearTimeout(timer);
  }, [copied]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(checkReport(turn));
      setCopied("copied");
    } catch {
      setCopied("failed");
    }
  }

  const Icon = copied === "copied" ? Check : Copy;
  return (
    <button
      type="button"
      onClick={copy}
      className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 dark:text-zinc-400 dark:hover:bg-zinc-900 dark:hover:text-zinc-200"
    >
      <Icon aria-hidden className="size-3.5" />
      <span aria-live="polite">
        {copied === "copied" ? "Copied" : copied === "failed" ? "Copy failed" : "Copy details"}
      </span>
    </button>
  );
}
