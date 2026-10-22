"use client";

import type { Turn } from "@/lib/chat-turn";
import { checkReport } from "@/lib/check-report";
import { useMessages } from "@/lib/messages";

import { CopyButton } from "./copy-button";

/** Copies the turn's answer, tool results and source-check verdicts as one report (#221). */
export function CopyCheckReport({ turn }: { turn: Turn }) {
  const t = useMessages();
  return (
    <CopyButton
      text={() => checkReport(turn, t)}
      label={t.check.copy}
      className="px-1.5 text-ink-3 hover:bg-panel hover:text-ink"
    />
  );
}
