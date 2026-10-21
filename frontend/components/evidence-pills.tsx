import { Box, Check, FileText } from "lucide-react";
import type { ReactNode } from "react";

import type { Turn } from "@/lib/chat-turn";
import { type EvidenceTab, shownSteps, sourceCards } from "@/lib/evidence";
import { useMessages } from "@/lib/messages";
import { stepLine } from "@/lib/step-line";
import { structuresOf } from "@/lib/tool-cards";

const PILL =
  "inline-flex h-7 items-center gap-1.5 rounded-full border border-rule-2 bg-card px-2.5 text-[12.5px] text-ink-2";

/**
 * Under the question: what the answer is doing while it comes in, then one pill each for its
 * steps, sources and 3D view, which open that tab of the evidence panel.
 */
export function EvidencePills({
  turn,
  onShow,
}: {
  turn: Turn;
  onShow: (tab: EvidenceTab) => void;
}) {
  const t = useMessages();
  if (turn.state === "queued") return null;
  // The sources arrive with the answer's last word; the source check after them has its own badge.
  if (turn.state === "answering" && turn.sources === null) {
    const last = turn.steps.at(-1);
    const current = turn.answer ? t.pills.writing : last ? stepLine(last, t) : t.pills.thinking;
    return (
      // Not a live region: the Steps tab announces the steps.
      <p className="flex h-7 items-center gap-2 text-[13px] text-ink-2">
        <span aria-hidden className="size-2 animate-pulse rounded-full bg-signal" />
        {current}…
      </p>
    );
  }

  const steps = shownSteps(turn).length;
  const sources = turn.sources ? sourceCards(turn.sources).length : 0;
  if (steps === 0 && sources === 0) return null;
  const structure = structuresOf(turn.steps)[0];
  return (
    <div className="flex flex-wrap gap-1.5">
      {steps > 0 && (
        <Pill onClick={() => onShow("steps")}>
          <Check aria-hidden strokeWidth={3} className="size-3 text-signal" />
          {t.pills.steps(steps)}
        </Pill>
      )}
      {sources > 0 && (
        <Pill onClick={() => onShow("sources")}>
          <FileText aria-hidden className="size-3.5" />
          {t.pills.sources(sources)}
        </Pill>
      )}
      {structure ? (
        <Pill onClick={() => onShow("3d")}>
          <Box aria-hidden className="size-3.5" />
          3D · {structure.complex?.pdb_id ?? t.pills.molecule}
        </Pill>
      ) : (
        <span className={`${PILL} opacity-55`}>
          <Box aria-hidden className="size-3.5" />
          {t.pills.no3d}
        </span>
      )}
    </div>
  );
}

function Pill({ onClick, children }: { onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`${PILL} hover:border-signal hover:text-signal focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3`}
    >
      {children}
    </button>
  );
}
