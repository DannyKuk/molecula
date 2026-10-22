import { cn } from "cn";

import { type Verdict, VERDICTS } from "@/lib/chat-model-benchmark";
import { type RankBand } from "@/lib/embedding-benchmark";

const RING = "size-3 ring-[1.5px] ring-ink-3 ring-inset";

const VERDICT_CLASSES: Record<Verdict, string> = {
  clean: "size-2 bg-ink-3/70",
  memory: "size-3 bg-verdict-memory",
  denies: "size-3 bg-verdict-denies",
  both: "size-3 bg-[linear-gradient(90deg,var(--verdict-memory)_50%,var(--verdict-denies)_50%)]",
  failed: RING,
};

const RANK_CLASSES: Record<RankBand, string> = {
  first: "size-3 bg-rank-first",
  top5: "size-3 bg-rank-top5",
  top10: "size-3 bg-rank-top10",
  missed: RING,
};

const RANK_LABELS: Record<RankBand, string> = {
  first: "Answer ranked 1st",
  top5: "2nd–5th (still a hit)",
  top10: "6th–10th (a miss at top 5)",
  missed: "Not in the top 10",
};

function Dot({ className }: { className: string }) {
  return <i aria-hidden className={cn("block rounded-full", className)} />;
}

/** One judged answer: a small grey dot when nothing was flagged, so the flags stand out. */
export function VerdictDot({ verdict, className }: { verdict: Verdict; className?: string }) {
  return <Dot className={cn(VERDICT_CLASSES[verdict], className)} />;
}

/** Where one model ranked the passage with the answer: darker is higher, a ring is a miss. */
export function RankDot({ band, className }: { band: RankBand; className?: string }) {
  return <Dot className={cn(RANK_CLASSES[band], className)} />;
}

function DotLegend({ items }: { items: [key: string, dot: React.ReactNode, label: string][] }) {
  return (
    <div className="flex flex-wrap items-center gap-x-3.5 gap-y-1.5 text-xs text-ink-2">
      {items.map(([key, dot, label]) => (
        <span key={key} className="inline-flex items-center gap-1.5">
          <span className="inline-flex size-3 items-center justify-center">{dot}</span>
          {label}
        </span>
      ))}
    </div>
  );
}

export function VerdictLegend({ verdicts }: { verdicts: Verdict[] }) {
  return (
    <DotLegend
      items={verdicts.map((verdict) => [
        verdict,
        <VerdictDot key={verdict} verdict={verdict} />,
        verdict === "both" ? "Both flags" : VERDICTS[verdict],
      ])}
    />
  );
}

export function RankLegend() {
  return (
    <DotLegend
      items={(Object.keys(RANK_LABELS) as RankBand[]).map((band) => [
        band,
        <RankDot key={band} band={band} />,
        RANK_LABELS[band],
      ])}
    />
  );
}
