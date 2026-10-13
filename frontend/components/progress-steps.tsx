"use client";

import { useId, useState } from "react";

type ProgressStepsProps = {
  steps: string[];
  /** Molecula is still answering: the list is live and the latest step is the current one. */
  live: boolean;
};

/** What Molecula is doing: a live list while it answers, then one line that opens the list. */
export function ProgressSteps({ steps, live }: ProgressStepsProps) {
  const [open, setOpen] = useState(false);
  const listId = useId();

  if (steps.length === 0) return null;
  if (live) {
    return (
      <ol aria-label="Progress" aria-live="polite" className="flex flex-col gap-1 text-sm">
        {steps.map((step, index) => (
          <Step key={index} text={step} current={index === steps.length - 1} />
        ))}
      </ol>
    );
  }
  return (
    <div className="flex flex-col gap-1 text-sm">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen(!open)}
        className="self-start text-zinc-600 underline-offset-4 hover:underline dark:text-zinc-400"
      >
        {stepCount(steps.length)}
      </button>
      {open && (
        <ol id={listId} aria-label="Progress" className="flex flex-col gap-1">
          {steps.map((step, index) => (
            <Step key={index} text={step} current={false} />
          ))}
        </ol>
      )}
    </div>
  );
}

function Step({ text, current }: { text: string; current: boolean }) {
  return (
    <li className="flex items-center gap-2 text-zinc-600 dark:text-zinc-400">
      <span
        aria-hidden
        className={`size-1.5 shrink-0 rounded-full ${current ? "animate-pulse bg-sky-500" : "bg-zinc-400"}`}
      />
      {text}
    </li>
  );
}

function stepCount(count: number): string {
  return `${count} ${count === 1 ? "step" : "steps"}`;
}
