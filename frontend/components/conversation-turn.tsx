import { cn } from "cn";

import type { Turn } from "@/lib/chat-turn";
import { didYouMeanOf } from "@/lib/did-you-mean";
import { checkingAnswer } from "@/lib/source-check";
import { structuresOf } from "@/lib/tool-cards";
import { formatUsage } from "@/lib/usage";

import { AnswerMarkdown } from "./answer-markdown";
import { AnswerSources, PrintedSources } from "./answer-sources";
import { CopyCheckReport } from "./copy-check-report";
import { DidYouMeanButtons } from "./did-you-mean";
import { ProgressSteps } from "./progress-steps";
import { SourceCheckBadge } from "./source-check-badge";
import { StructurePanel } from "./structure/structure-panel";

type ConversationTurnProps = {
  turn: Turn;
  /** The question's place in the conversation, from 1. */
  number: number;
  /** The turn the reader is on: its label lights up. */
  active: boolean;
  /** Asks a new question, from a suggested name for one the tools didn't find. */
  onAsk: (question: string) => void;
  /** Whether any turn's answer is still coming in. */
  chatAnswering: boolean;
  /** Set on the latest turn only, when it failed. */
  onRetry?: () => void;
};

/** One question, the steps taken for it and the answer as far as it has arrived. */
export function ConversationTurn({
  turn,
  number,
  active,
  onAsk,
  chatAnswering,
  onRetry,
}: ConversationTurnProps) {
  const answering = turn.state === "answering";
  const offers = answering ? [] : didYouMeanOf(turn.question, turn.steps);
  return (
    <li
      data-turn
      className={cn(
        "relative flex flex-col gap-3 print:break-inside-avoid print:border-t print:pt-6",
        active && "before:absolute before:inset-y-0 before:-left-4 before:w-px before:bg-signal",
        "print:before:hidden",
      )}
    >
      <TurnLabel number={number} active={active} />
      <PrintedSpeaker>You</PrintedSpeaker>
      <h2 className="mb-1 text-[27px] leading-tight font-semibold tracking-tight break-words whitespace-pre-wrap print:text-base">
        {turn.question}
      </h2>
      <div className="contents print:hidden">
        <ProgressSteps steps={turn.steps} live={answering} answer={turn.answer} />
        {/* Above the answer, so the streaming text doesn't push the 3D view off screen. */}
        {structuresOf(turn.steps).map((target) => (
          <StructurePanel key={target.cid} target={target} />
        ))}
      </div>
      {(turn.answer || !answering) && <PrintedSpeaker>Molecula</PrintedSpeaker>}
      {answering && turn.steps.length === 0 && !turn.answer && (
        <p role="status" className="text-sm text-ink-2">
          Thinking…
        </p>
      )}
      {turn.state === "queued" && (
        <p role="status" className="text-sm text-ink-2">
          Waiting for the answer in another chat to finish…
        </p>
      )}
      {turn.answer && (
        <AnswerMarkdown
          text={turn.answer}
          citations={turn.sources && { sources: turn.sources, passages: turn.passages }}
          sourceCheck={turn.sourceCheck}
        />
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
      {turn.sources && <AnswerSources answer={turn.answer} sources={turn.sources} />}
      {turn.usage && (
        <p className="font-mono text-[11px] text-ink-3 tabular-nums print:hidden">
          {formatUsage(turn.usage)}
        </p>
      )}
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

/** "Q-01 · Query" with a status light, lit on the turn the reader is on. */
function TurnLabel({ number, active }: { number: number; active: boolean }) {
  return (
    <p
      className={cn(
        "flex items-center gap-2 font-mono text-[11px] tracking-wider uppercase print:hidden",
        active ? "text-ink" : "text-ink-3",
      )}
    >
      <span
        aria-hidden
        className={cn("size-[5px] rounded-full", active ? "bg-signal" : "bg-rule-2")}
      />
      Q-{String(number).padStart(2, "0")} · Query
    </p>
  );
}

/**
 * Who wrote the message below it, on paper only, where the question prints at the answer's size
 * and without its label.
 */
function PrintedSpeaker({ children }: { children: string }) {
  return (
    <p className="hidden text-xs font-semibold text-ink-2 print:-mb-2 print:block">{children}</p>
  );
}
