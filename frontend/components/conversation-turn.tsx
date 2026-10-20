import { cn } from "cn";

import type { Turn } from "@/lib/chat-turn";
import { didYouMeanOf } from "@/lib/did-you-mean";
import type { EvidenceTab } from "@/lib/evidence";
import type { Pictures } from "@/lib/printed-pictures";
import { checkingAnswer } from "@/lib/source-check";
import { structuresOf } from "@/lib/tool-cards";
import { formatUsage } from "@/lib/usage";

import { AnswerMarkdown } from "./answer-markdown";
import { OpenCitedSources } from "./citation-chip";
import { CopyCheckReport } from "./copy-check-report";
import { DidYouMeanButtons } from "./did-you-mean";
import { EvidencePills } from "./evidence-pills";
import { askedTime, PrintedSources, PrintedStructure } from "./printed-conversation";
import { SourceCheckBadge } from "./source-check-badge";

type ConversationTurnProps = {
  turn: Turn;
  /** The question's place in the conversation, from 1. */
  number: number;
  /** The turn the evidence panel shows: its label lights up. */
  active: boolean;
  /** Opens a tab of the evidence panel on this turn, on the cited sources for a citation chip. */
  onShow: (tab: EvidenceTab, refs?: number[]) => void;
  /** Asks a new question, from a suggested name for one the tools didn't find. */
  onAsk: (question: string) => void;
  /** Whether any turn's answer is still coming in. */
  chatAnswering: boolean;
  /** Set on the latest turn only, when it failed. */
  onRetry?: () => void;
  /** The pictures of the 3D structures for paper, by CID. */
  pictures: Pictures;
};

/**
 * One question and the answer as far as it has arrived, with pills that open its steps, sources
 * and 3D view in the evidence panel.
 */
export function ConversationTurn({
  turn,
  number,
  active,
  onShow,
  onAsk,
  chatAnswering,
  onRetry,
  pictures,
}: ConversationTurnProps) {
  const answering = turn.state === "answering";
  const offers = answering ? [] : didYouMeanOf(turn.question, turn.steps);
  return (
    <li
      data-turn
      aria-current={active || undefined}
      className={cn(
        "relative flex flex-col gap-3",
        active && "before:absolute before:inset-y-0 before:-left-4 before:w-px before:bg-signal",
      )}
    >
      <TurnLabel number={number} active={active} askedAt={turn.askedAt} />
      <h2 className="mb-1 text-[27px] leading-tight font-semibold tracking-tight break-words whitespace-pre-wrap">
        {turn.question}
      </h2>
      <div className="contents print:hidden">
        <EvidencePills turn={turn} onShow={onShow} />
      </div>
      {turn.state === "queued" && (
        <p role="status" className="text-sm text-ink-2">
          Waiting for the answer in another chat to finish…
        </p>
      )}
      {turn.answer && (
        <OpenCitedSources value={(refs) => onShow("sources", refs)}>
          <AnswerMarkdown
            text={turn.answer}
            citations={turn.sources && { sources: turn.sources, passages: turn.passages }}
            sourceCheck={turn.sourceCheck}
          />
        </OpenCitedSources>
      )}
      {turn.answer && (
        <div className="flex flex-wrap items-center gap-2 empty:hidden">
          <SourceCheckBadge check={turn.sourceCheck} checking={checkingAnswer(turn)} />
          {turn.sourceCheck && (
            <div className="contents print:hidden">
              <CopyCheckReport turn={turn} />
            </div>
          )}
        </div>
      )}
      {turn.usage && (
        <p className="font-mono text-[11px] text-ink-3 tabular-nums print:hidden">
          {formatUsage(turn.usage)}
        </p>
      )}
      {structuresOf(turn.steps).map((target) => (
        <PrintedStructure key={target.cid} target={target} picture={pictures.get(target.cid)} />
      ))}
      {turn.sources && <PrintedSources sources={turn.sources} />}
      {offers.length > 0 && (
        <div className="contents print:hidden">
          <DidYouMeanButtons offers={offers} onAsk={onAsk} disabled={chatAnswering} />
        </div>
      )}
      {turn.state === "stopped" && <p className="text-sm text-ink-2">Stopped.</p>}
      {turn.state === "failed" && (
        <div
          role="alert"
          className="flex flex-wrap items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800 dark:border-red-900 dark:bg-red-950 dark:text-red-300"
        >
          <span>{turn.error}</span>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="font-medium underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-500 print:hidden"
            >
              Try again
            </button>
          )}
        </div>
      )}
    </li>
  );
}

/** "Q-01 · Query" with a status light, lit on the turn the reader is on. Paper adds when the
 * question was asked. */
function TurnLabel({
  number,
  active,
  askedAt,
}: {
  number: number;
  active: boolean;
  askedAt?: number;
}) {
  return (
    <p
      data-turn-label
      className={cn(
        "flex items-center gap-2 font-mono text-[11px] tracking-wider uppercase",
        active ? "text-ink" : "text-ink-3",
      )}
    >
      <span
        aria-hidden
        className={cn("size-[5px] rounded-full print:hidden", active ? "bg-signal" : "bg-rule-2")}
      />
      Q-{String(number).padStart(2, "0")} · Query
      {askedAt !== undefined && (
        <span className="ml-auto hidden text-ink-3 tabular-nums print:inline">
          {askedTime(askedAt)}
        </span>
      )}
    </p>
  );
}
