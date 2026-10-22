import { cn } from "cn";

import type { Who } from "@/lib/answer-flow";
import { useMessages } from "@/lib/messages";

export const WHO_COLOURS: Record<Who, { tag: string; mark: string }> = {
  model: { tag: "border-signal bg-signal-soft text-signal", mark: "bg-signal" },
  embedder: {
    tag: "border-series-drug bg-series-drug/12 text-series-drug",
    mark: "bg-series-drug",
  },
  code: { tag: "border-rule-2 bg-panel text-ink-2", mark: "bg-ink-3" },
};

/** Who does a step, as a small coloured tag; the word carries the meaning, the colour repeats it.
 * `label` replaces the word when the step can be done by either of two models. */
export function WhoTag({ who, label }: { who: Who; label?: string }) {
  const t = useMessages();
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-1.5 py-px font-mono text-[10.5px] tracking-wider whitespace-nowrap uppercase",
        WHO_COLOURS[who].tag,
      )}
    >
      <span aria-hidden className="size-1.5 rounded-full bg-current" />
      {label ?? t.flow.who[who]}
    </span>
  );
}
