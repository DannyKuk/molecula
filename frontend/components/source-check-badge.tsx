import { LoaderCircle, Shield, ShieldAlert, ShieldCheck } from "lucide-react";

import type { SourceCheck } from "@/lib/chat";
import { CHECKING_ANSWER, checkSummary, type CheckSummary } from "@/lib/source-check";

const BADGE =
  "inline-flex flex-wrap items-center gap-x-2 gap-y-0.5 rounded-2xl border px-3 py-1 text-sm";

const TONES: Record<CheckSummary["kind"] | "checking", string> = {
  checking: "border-rule bg-card text-ink-2 [&_svg]:text-signal",
  backed: "border-rule bg-card text-ink-2 [&_svg]:text-ok",
  unbacked:
    "border-amber-200 bg-amber-50 text-amber-900 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-200",
  unchecked: "border-rule bg-card text-ink-2",
};

const ICONS = { backed: ShieldCheck, unbacked: ShieldAlert, unchecked: Shield };

/** The badge under the answer: it says the answer is being checked against its sources, then
 * what the check found. */
export function SourceCheckBadge({
  check,
  checking,
}: {
  check: SourceCheck | null;
  checking: boolean;
}) {
  const summary = check && checkSummary(check);
  if (!checking && !summary) return null;
  return (
    <div role="status" data-source-check className="self-start">
      {checking || !summary ? (
        <p className={`${BADGE} ${TONES.checking}`}>
          <LoaderCircle aria-hidden className="size-4 shrink-0 animate-spin" />
          {CHECKING_ANSWER}…
        </p>
      ) : (
        <Summary summary={summary} />
      )}
    </div>
  );
}

function Summary({ summary }: { summary: CheckSummary }) {
  const Icon = ICONS[summary.kind];
  return (
    <p className={`${BADGE} ${TONES[summary.kind]}`}>
      <Icon aria-hidden className="size-4 shrink-0" />
      <span className="font-medium">{summary.title}</span>
      {summary.detail && <span>· {summary.detail}</span>}
    </p>
  );
}
