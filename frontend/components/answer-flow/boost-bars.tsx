import { cn } from "cn";

import { type RankedPassage } from "@/lib/answer-flow";
import type { Messages } from "@/lib/messages";

/**
 * The passages a search kept, best first: the similarity as a grey bar, the section bonus as an
 * orange end, the score and the place before and after the bonus. The bars run from 0 to the best
 * score rounded up to a tenth, so the bonus is wide enough to see.
 */
export function BoostBars({
  passages,
  boost,
  t,
}: {
  passages: RankedPassage[];
  boost: number;
  t: Messages;
}) {
  const bars = t.flow.bars;
  const ordinal = bars.ordinal;
  if (passages.length === 0) return null;
  const bonused = (passage: RankedPassage) => boost > 0 && passage.inSection;
  const top = Math.max(...passages.map((passage) => passage.score));
  const scale = Math.ceil(top * 10) / 10;
  const width = (value: number) => `${(value / scale) * 100}%`;
  return (
    <div className="flex flex-col gap-2">
      <ol aria-label={bars.label} className="flex flex-col">
        {passages.map((passage) => (
          <li
            key={`${passage.before}`}
            className="grid grid-cols-[minmax(0,1fr)_4.5rem] items-center gap-x-3 gap-y-1.5 border-t border-rule py-2 first:border-t-0 sm:grid-cols-[minmax(0,1.2fr)_minmax(0,1.6fr)_4.5rem]"
          >
            <span className="col-start-1 row-start-1 min-w-0 text-[13px]">
              {passage.section}
              <span
                className={cn(
                  "block font-mono text-[10.5px]",
                  bonused(passage) ? "text-signal" : "text-ink-3",
                )}
              >
                {bonused(passage) ? bars.sectionAskedFor(boost.toFixed(2)) : bars.noBonus}
              </span>
            </span>
            <span
              aria-hidden
              className="relative col-span-2 col-start-1 row-start-2 h-2 rounded-sm bg-rule sm:col-span-1 sm:col-start-2 sm:row-start-1"
            >
              <span
                className="absolute inset-y-0 left-0 rounded-l-sm bg-ink-3"
                style={{ width: width(passage.similarity) }}
              />
              {bonused(passage) && (
                <span
                  className="absolute inset-y-0 rounded-r-sm bg-signal"
                  style={{ left: width(passage.similarity), width: width(boost) }}
                />
              )}
            </span>
            <span className="col-start-2 row-start-1 text-right font-mono text-[12px] tabular-nums sm:col-start-3">
              {passage.score.toFixed(2)}
              <span className="block text-[10.5px] text-ink-3">
                {passage.before === passage.after
                  ? ordinal(passage.after)
                  : `${ordinal(passage.before)} → ${ordinal(passage.after)}`}
              </span>
            </span>
          </li>
        ))}
      </ol>
      <p className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-ink-3">
        <span className="inline-flex items-center gap-1.5">
          <span aria-hidden className="h-2 w-3 rounded-sm bg-ink-3" />
          {bars.similarity}
        </span>
        {boost > 0 && (
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden className="h-2 w-3 rounded-sm bg-signal" />
            {bars.bonus}
          </span>
        )}
        <span>{bars.scale(scale.toFixed(1))}</span>
      </p>
    </div>
  );
}
