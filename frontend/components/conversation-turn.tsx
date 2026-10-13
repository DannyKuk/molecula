import type { Turn } from "@/lib/chat-turn";
import { structuresOf } from "@/lib/tool-cards";

import { AnswerMarkdown } from "./answer-markdown";
import { AnswerSources } from "./answer-sources";
import { ProgressSteps } from "./progress-steps";
import { StructurePanel } from "./structure/structure-panel";

type ConversationTurnProps = {
  turn: Turn;
  /** Set on the latest turn only, when it failed. */
  onRetry?: () => void;
};

/** One question, the steps taken for it and the answer as far as it has arrived. */
export function ConversationTurn({ turn, onRetry }: ConversationTurnProps) {
  const answering = turn.state === "answering";
  return (
    <li data-turn className="flex flex-col gap-3">
      <p className="max-w-[85%] self-end rounded-2xl bg-zinc-100 px-4 py-2 break-words whitespace-pre-wrap dark:bg-zinc-900">
        {turn.question}
      </p>
      <ProgressSteps steps={turn.steps} live={answering} answer={turn.answer} />
      {/* Above the answer, so the streaming text doesn't push the 3D view off screen. */}
      {structuresOf(turn.steps).map((target) => (
        <StructurePanel key={target.cid} target={target} />
      ))}
      {answering && turn.steps.length === 0 && !turn.answer && (
        <p role="status" className="text-sm text-zinc-600 dark:text-zinc-400">
          Thinking…
        </p>
      )}
      {turn.answer && (
        <AnswerMarkdown
          text={turn.answer}
          citations={turn.sources && { sources: turn.sources, passages: turn.passages }}
        />
      )}
      {turn.sources && (
        <AnswerSources answer={turn.answer} sources={turn.sources} disclaimer={turn.disclaimer} />
      )}
      {turn.state === "stopped" && (
        <p className="text-sm text-zinc-600 dark:text-zinc-400">Stopped.</p>
      )}
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
              className="font-medium underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-red-500"
            >
              Try again
            </button>
          )}
        </div>
      )}
    </li>
  );
}
