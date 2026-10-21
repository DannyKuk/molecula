import { cn } from "cn";
import Link from "next/link";

import type { Turn } from "@/lib/chat-turn";
import { type Messages, useMessages } from "@/lib/messages";
import { type TurnStep, type TurnStepState, turnFlow } from "@/lib/turn-flow";

import { BoostBars } from "./boost-bars";
import { FlowLineStep } from "./flow-line";

const FADED: TurnStepState[] = ["skipped", "waiting", "not_reached"];

/** The flow one answer took, step by step from its own events, each step tagged by who did it
 * and linked to the guide's explanation of it. */
export function FlowTab({ turn }: { turn: Turn }) {
  const t = useMessages();
  return (
    <div className="flex flex-col gap-4">
      <p className="text-[13px] text-ink-2">
        {t.flow.intro}{" "}
        <Link href="/how-it-answers" className="font-medium underline underline-offset-4">
          {t.flow.guideLink}
        </Link>{" "}
        {t.flow.guideAfter}
      </p>
      {turnFlow(turn, t).map((part, index) => (
        <div key={part.steps[0]?.key ?? index} className="flex flex-col gap-2">
          {part.title && (
            <p className="border-t border-rule pt-3 font-mono text-[11px] tracking-wider text-ink-3 uppercase">
              {part.title}
            </p>
          )}
          <ol aria-label={part.title ?? t.flow.steps} className="flex flex-col">
            {part.steps.map((step) => (
              <FlowStepItem key={step.key} step={step} t={t} />
            ))}
          </ol>
        </div>
      ))}
    </div>
  );
}

function FlowStepItem({ step, t }: { step: TurnStep; t: Messages }) {
  const state = step.state === "done" ? null : t.flow.states[step.state];
  return (
    <FlowLineStep
      number={step.number}
      title={step.title}
      who={step.who}
      whoLabel={step.whoLabel ?? t.flow.who[step.who]}
      faded={FADED.includes(step.state)}
      current={step.state === "running"}
      status={
        state && (
          <span
            className={cn(
              "rounded-full border px-1.5 font-mono text-[10px] tracking-wider uppercase",
              step.state === "failed" || step.state === "stopped"
                ? "border-signal text-signal"
                : "border-rule-2 text-ink-3",
            )}
          >
            {state}
          </span>
        )
      }
    >
      <p className="text-[13px] text-ink-3">{step.line}</p>
      {step.call && <code className="font-mono text-[12px] break-words">{step.call}</code>}
      {step.outcome && <p>{step.outcome}</p>}
      {step.ranking && (
        <BoostBars passages={step.ranking.passages} boost={step.ranking.boost} t={t} />
      )}
      {step.guide && (
        <Link
          href={`/how-it-answers#${step.guide}`}
          className="self-start text-xs text-ink-2 underline underline-offset-4 hover:text-ink"
        >
          {t.flow.whatThisMeans}
        </Link>
      )}
    </FlowLineStep>
  );
}
