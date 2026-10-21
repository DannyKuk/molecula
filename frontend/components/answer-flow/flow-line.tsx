import { cn } from "cn";
import type { ReactNode } from "react";

import type { Who } from "@/lib/answer-flow";

import { WHO_COLOURS, WhoTag } from "./who-tag";

/**
 * One step on the flow's line, drawn like a step on the Steps tab: a mark and its title, the text
 * beside a thin rule, and what it hands to the next step at the foot of the rule. A `faded` step
 * didn't run: its mark is hollow and its title grey. A `current` one is running: its mark pulses.
 */
export function FlowLineStep({
  id,
  number,
  title,
  who,
  whoLabel,
  status,
  faded = false,
  current = false,
  passes,
  children,
}: {
  id?: string;
  number: string;
  title: string;
  who: Who | null;
  whoLabel?: string;
  status?: ReactNode;
  faded?: boolean;
  current?: boolean;
  passes?: string;
  children: ReactNode;
}) {
  return (
    <li id={id} className="group grid scroll-mt-6 grid-cols-[0.75rem_minmax(0,1fr)] gap-x-3">
      <span
        aria-hidden
        className={cn(
          "mt-[0.4rem] size-2.5 rounded-full",
          who && !faded ? WHO_COLOURS[who].mark : "border border-ink-3",
          current && "animate-pulse",
        )}
      />
      <h3 className="flex flex-wrap items-center gap-x-2.5 gap-y-1">
        <span className="font-mono text-xs text-ink-3">{number}</span>
        <span className={cn("text-[15px] font-semibold", faded && "text-ink-3")}>{title}</span>
        {who && <WhoTag who={who} label={whoLabel} />}
        {status}
      </h3>
      <span aria-hidden className="w-px justify-self-center bg-rule-2 group-last:invisible" />
      <div className="flex min-w-0 flex-col gap-1.5 pt-1.5 pb-5 text-sm">
        {children}
        {passes && (
          <p className="pt-1 font-mono text-[11.5px] break-words text-ink-3">
            <span aria-hidden>↓ </span>
            {passes}
          </p>
        )}
      </div>
    </li>
  );
}
