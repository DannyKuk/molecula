"use client";

import { createContext, useContext, type ReactNode } from "react";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { Source } from "@/lib/chat";
import {
  citedSources,
  excerpt,
  isLabel,
  labelDate,
  sectionName,
  siteName,
  sourceLabel,
  type Citations,
} from "@/lib/citations";
import { useMessages } from "@/lib/messages";

/** The answer's sources and passages, or null while the answer is still streaming. */
export const CitationsContext = createContext<Citations | null>(null);

/** Opens the evidence panel's Sources tab on the cited sources, or null where there is no panel. */
export const OpenCitedSources = createContext<((refs: number[]) => void) | null>(null);

/**
 * A run of citations such as `[2][3]` as one chip naming the first source it cites (a label
 * section, or a PubChem, ChEMBL or RCSB page), with "+1" for each other one. Its popover shows
 * every cited passage with a link to the label on DailyMed, and every cited page with its link;
 * clicking it opens them on the evidence panel's Sources tab. While the answer streams the
 * citation stays as written; a number that points at no passage is left out. `spaced` says a space stood before the citation; it is kept
 * with the chip and left out with it. A `found` chip is one the answer didn't write: the source
 * check found these results hold the sentence before it (#220).
 */
export function CitationChip({
  refs,
  spaced,
  found = false,
  children,
}: {
  refs: number[];
  spaced: boolean;
  found?: boolean;
  children: ReactNode;
}) {
  const t = useMessages();
  const citations = useContext(CitationsContext);
  const openSources = useContext(OpenCitedSources);
  if (!citations) return <>{children}</>;
  const sources = citedSources(refs, citations.sources);
  if (sources.length === 0) return null;
  const labels = [...new Set(sources.map(sourceLabel))];
  const others = labels.length > 1 ? ` +${labels.length - 1}` : "";
  return (
    <>
      {spaced && " "}
      <Popover
        onOpenChange={(_open, details) => {
          // A click opens the Sources tab instead; on a phone the popover would cover its sheet.
          if (openSources && details.reason === "trigger-press") details.cancel();
        }}
      >
        <PopoverTrigger
          openOnHover
          delay={150}
          onClick={() => openSources?.(refs)}
          aria-label={`${found ? t.sources.found : t.sources.sources}: ${labels.join(", ")}`}
          className="mx-0.5 inline-flex max-w-full items-center gap-1.5 rounded-md bg-panel py-0.5 pr-2 pl-1.5 align-middle text-xs font-medium text-ink-2 hover:bg-ink hover:text-page focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3 print:hidden"
        >
          {sources[0].ref !== null && (
            <span aria-hidden className="font-mono text-[10.5px] font-semibold text-signal">
              {sources[0].ref}
            </span>
          )}
          <span className="truncate">{labels[0]}</span>
          {others}
        </PopoverTrigger>
        <PopoverContent align="start" className="max-h-96 w-80 gap-0 overflow-y-auto p-0">
          {found && (
            <p className="px-3 pt-3 text-xs text-muted-foreground">{t.sources.foundNote}</p>
          )}
          <ol className="divide-y divide-border">
            {sources.map((source) => (
              <li key={source.ref} className="flex flex-col gap-1 p-3">
                {isLabel(source) ? (
                  <CitedPassage source={source} text={citations.passages[source.ref!]?.text} />
                ) : (
                  <CitedPage source={source} />
                )}
              </li>
            ))}
          </ol>
        </PopoverContent>
      </Popover>
      <span className="hidden print:inline">[{printedRefs(sources)}]</span>
    </>
  );
}

function CitedPassage({ source, text }: { source: Source; text?: string }) {
  const t = useMessages();
  return (
    <>
      <p className="font-medium">
        {source.name} · {sectionName(source.section)}
      </p>
      {source.effective_time && (
        <p className="text-xs text-muted-foreground">
          {t.sources.labelOf(labelDate(source.effective_time, t.locale))}
        </p>
      )}
      {text && <p className="border-l-2 border-signal pl-2 text-ink-2">{excerpt(text)}</p>}
      <a
        href={source.url}
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium underline underline-offset-4"
      >
        {t.sources.openLabel}
      </a>
    </>
  );
}

function CitedPage({ source }: { source: Source }) {
  const t = useMessages();
  return (
    <>
      <p className="font-medium">{sourceLabel(source)}</p>
      <a
        href={source.url}
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium underline underline-offset-4"
      >
        {t.sources.openOn(siteName(source))}
      </a>
    </>
  );
}

/** "2, 3": the numbers the printed source list gives these sources. */
function printedRefs(sources: Source[]): string {
  return [...new Set(sources.map((source) => source.ref))].join(", ");
}
