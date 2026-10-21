"use client";

import { Check, Copy } from "lucide-react";
import { useEffect, useState } from "react";

import type { Turn } from "@/lib/chat-turn";
import { checkReport } from "@/lib/check-report";
import { useMessages } from "@/lib/messages";

const SHOWN_MS = 2000;

/** Copies the turn's answer, tool results and source-check verdicts as one report (#221). */
export function CopyCheckReport({ turn }: { turn: Turn }) {
  const t = useMessages();
  const [copied, setCopied] = useState<"copied" | "failed" | null>(null);

  useEffect(() => {
    if (!copied) return;
    const timer = setTimeout(() => setCopied(null), SHOWN_MS);
    return () => clearTimeout(timer);
  }, [copied]);

  async function copy() {
    try {
      await navigator.clipboard.writeText(checkReport(turn, t));
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
      className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-xs text-ink-3 hover:bg-panel hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3"
    >
      <Icon aria-hidden className="size-3.5" />
      <span aria-live="polite">
        {copied === "copied"
          ? t.check.copied
          : copied === "failed"
            ? t.check.copyFailed
            : t.check.copy}
      </span>
    </button>
  );
}
