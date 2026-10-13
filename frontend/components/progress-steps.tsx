"use client";

import { useId, useState } from "react";

import { cardSteps, type CardStep, type Step } from "@/lib/tool-cards";

import { ToolCard } from "./tool-cards/tool-card";

type ProgressStepsProps = {
  steps: Step[];
  /** Molecula is still answering: the list is live and the latest step is the current one. */
  live: boolean;
  /** The answer so far, to mark the label passages it cites. */
  answer: string;
};

/**
 * What Molecula is doing: a live list while it answers, then one line that opens the list.
 * A step whose tool has returned opens into what it returned. Properties looked up drug by drug
 * are merged into one table once the answer is done, so the list doesn't jump while it streams.
 */
export function ProgressSteps({ steps, live, answer }: ProgressStepsProps) {
  const [open, setOpen] = useState(false);
  const listId = useId();

  if (steps.length === 0) return null;
  const shown = cardSteps(steps, !live);
  if (live) {
    return (
      <ol aria-label="Progress" aria-live="polite" className="flex flex-col gap-1.5 text-sm">
        {shown.map((step, index) => (
          <StepRow key={index} step={step} current={index === shown.length - 1} answer={answer} />
        ))}
      </ol>
    );
  }
  return (
    <div className="flex flex-col gap-1.5 text-sm">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen(!open)}
        className="self-start text-zinc-600 underline-offset-4 hover:underline dark:text-zinc-400"
      >
        {stepCount(shown.length)}
      </button>
      {open && (
        <ol id={listId} aria-label="Progress" className="flex flex-col gap-1.5">
          {shown.map((step, index) => (
            <StepRow key={index} step={step} current={false} answer={answer} />
          ))}
        </ol>
      )}
    </div>
  );
}

function StepRow({ step, current, answer }: { step: CardStep; current: boolean; answer: string }) {
  if (step.card && step.card.kind !== "pending") {
    return (
      <li>
        <ToolCard text={step.text} card={step.card} answer={answer} />
      </li>
    );
  }
  return (
    <li className="flex items-center gap-2 text-zinc-600 dark:text-zinc-400">
      <span
        aria-hidden
        className={`size-1.5 shrink-0 rounded-full ${current ? "animate-pulse bg-sky-500" : "bg-zinc-400"}`}
      />
      {step.text}
    </li>
  );
}

function stepCount(count: number): string {
  return `${count} ${count === 1 ? "step" : "steps"}`;
}
