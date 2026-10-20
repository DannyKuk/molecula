"use client";

import { createContext, useContext, type ReactNode } from "react";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { Source } from "@/lib/chat";
import {
  citedSources,
  isLabel,
  labelDate,
  sectionName,
  siteName,
  sourceLabel,
  type Citations,
} from "@/lib/citations";

/** The answer's sources and passages, or null while the answer is still streaming. */
export const CitationsContext = createContext<Citations | null>(null);

const EXCERPT_LENGTH = 320;

/**
 * A run of citations such as `[2][3]` as one chip naming the first source it cites (a label
 * section, or a PubChem, ChEMBL or RCSB page), with "+1" for each other one. Its popover shows
 * every cited passage with a link to the label on DailyMed, and every cited page with its link. While the answer streams the citation stays as written; a number that
 * points at no passage is left out. `spaced` says a space stood before the citation; it is kept
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
  const citations = useContext(CitationsContext);
  if (!citations) return <>{children}</>;
  const sources = citedSources(refs, citations.sources);
  if (sources.length === 0) return null;
  const labels = [...new Set(sources.map(sourceLabel))];
  const others = labels.length > 1 ? ` +${labels.length - 1}` : "";
  return (
    <>
      {spaced && " "}
      <Popover>
        <PopoverTrigger
          openOnHover
          delay={150}
          aria-label={`${found ? "Found by the source check" : "Sources"}: ${labels.join(", ")}`}
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
            <p className="px-3 pt-3 text-xs text-muted-foreground">
              The answer didn&apos;t cite this; the source check found the sentence here.
            </p>
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
  return (
    <>
      <p className="font-medium">
        {source.name} · {sectionName(source.section)}
      </p>
      {source.effective_time && (
        <p className="text-xs text-muted-foreground">
          FDA label of {labelDate(source.effective_time)}
        </p>
      )}
      {text && <p className="border-l-2 border-signal pl-2 text-ink-2">{excerpt(text)}</p>}
      <a
        href={source.url}
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium underline underline-offset-4"
      >
        Open the label on DailyMed
      </a>
    </>
  );
}

function CitedPage({ source }: { source: Source }) {
  return (
    <>
      <p className="font-medium">{sourceLabel(source)}</p>
      <a
        href={source.url}
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium underline underline-offset-4"
      >
        Open on {siteName(source)}
      </a>
    </>
  );
}

/** "2, 3": the numbers the printed source list gives these sources. */
function printedRefs(sources: Source[]): string {
  return [...new Set(sources.map((source) => source.ref))].join(", ");
}

function excerpt(text: string): string {
  return text.length > EXCERPT_LENGTH ? `${text.slice(0, EXCERPT_LENGTH).trimEnd()}…` : text;
}
