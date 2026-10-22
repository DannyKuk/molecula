import { cn } from "cn";

import { type Verdict, VERDICTS } from "@/lib/chat-model-benchmark";

const DOT_CLASSES: Record<Verdict, string> = {
  clean: "size-2 bg-ink-3/70",
  memory: "size-3 bg-verdict-memory",
  denies: "size-3 bg-verdict-denies",
  both: "size-3 bg-[linear-gradient(90deg,var(--verdict-memory)_50%,var(--verdict-denies)_50%)]",
  failed: "size-3 ring-[1.5px] ring-ink-3 ring-inset",
};

/** One judged answer: a small grey dot when nothing was flagged, so the flags stand out. */
export function VerdictDot({ verdict, className }: { verdict: Verdict; className?: string }) {
  return <i aria-hidden className={cn("block rounded-full", DOT_CLASSES[verdict], className)} />;
}

export function VerdictLegend({ verdicts }: { verdicts: Verdict[] }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3.5 gap-y-1.5 text-xs text-ink-2">
      {verdicts.map((verdict) => (
        <span key={verdict} className="inline-flex items-center gap-1.5">
          <span className="inline-flex size-3 items-center justify-center">
            <VerdictDot verdict={verdict} />
          </span>
          {verdict === "both" ? "Both flags" : VERDICTS[verdict]}
        </span>
      ))}
    </div>
  );
}
