"use client";

import { useMessages } from "@/lib/messages";
import type { CardStep, Step } from "@/lib/tool-cards";
import { cardSteps } from "@/lib/tool-cards";

import { StepDot } from "./step-dot";
import { ToolCard } from "./tool-cards/tool-card";

type ProgressStepsProps = {
  steps: Step[];
  /** Molecula is still answering: the list is live and the latest step is the current one. */
  live: boolean;
  /** The answer so far, to mark the label passages it cites. */
  answer: string;
};

/**
 * What Molecula did for an answer, live while it answers. A step whose tool has returned opens
 * into what it returned. Properties looked up drug by drug are merged into one table once the
 * answer is done, so the list doesn't jump while it streams.
 */
export function ProgressSteps({ steps, live, answer }: ProgressStepsProps) {
  const t = useMessages();
  if (steps.length === 0) return null;
  const shown = cardSteps(steps, !live, t);
  return (
    <ol
      aria-label={t.progress.label}
      aria-live={live ? "polite" : undefined}
      className="flex flex-col gap-1 text-sm"
    >
      {shown.map((step, index) => (
        <StepRow
          key={index}
          step={step}
          current={live && index === shown.length - 1}
          answer={answer}
        />
      ))}
    </ol>
  );
}

function StepRow({ step, current, answer }: { step: CardStep; current: boolean; answer: string }) {
  if (step.card && step.card.kind !== "pending") {
    return (
      <li>
        <ToolCard text={step.text} card={step.card} answer={answer} current={current} />
      </li>
    );
  }
  return (
    <li className="flex items-center gap-2 text-ink-2">
      <StepDot current={current} />
      {step.text}
    </li>
  );
}
