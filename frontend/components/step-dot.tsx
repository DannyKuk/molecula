import { Check } from "lucide-react";

/** The mark before a progress step: a pulsing dot on the step Molecula is working on, else a tick. */
export function StepDot({ current }: { current: boolean }) {
  if (!current)
    return <Check aria-hidden strokeWidth={3} className="size-3 shrink-0 text-signal" />;
  return (
    <span aria-hidden className="grid size-3 shrink-0 place-items-center">
      <span className="size-1.5 animate-pulse rounded-full bg-signal" />
    </span>
  );
}
