"use client";

import { createContext, useContext, type ReactNode } from "react";

import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import type { Source } from "@/lib/chat";
import { citedSources, labelDate, sectionName, sourceLabel, type Citations } from "@/lib/citations";

/** The answer's sources and passages, or null while the answer is still streaming. */
export const CitationsContext = createContext<Citations | null>(null);

const EXCERPT_LENGTH = 320;

/**
 * A run of citations such as `[2][3]` as one chip naming the first label section it cites,
 * with "+1" for each other section. Its popover shows every cited passage with a link to the
 * label on DailyMed. While the answer streams the citation stays as written; a number that
 * points at no passage is left out. `spaced` says a space stood before the citation; it is kept
 * with the chip and left out with it.
 */
export function CitationChip({
  refs,
  spaced,
  children,
}: {
  refs: number[];
  spaced: boolean;
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
          aria-label={`Sources: ${labels.join(", ")}`}
          className="mx-0.5 inline-flex max-w-full items-center rounded-full border border-zinc-300 bg-zinc-100 px-2 py-0.5 align-middle text-xs font-medium hover:bg-zinc-200 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 dark:border-zinc-700 dark:bg-zinc-900 dark:hover:bg-zinc-800"
        >
          <span className="truncate">{labels[0]}</span>
          {others}
        </PopoverTrigger>
        <PopoverContent align="start" className="max-h-96 w-80 gap-0 overflow-y-auto p-0">
          <ol className="divide-y divide-border">
            {sources.map((source) => (
              <li key={source.ref} className="flex flex-col gap-1 p-3">
                <CitedPassage source={source} text={citations.passages[source.ref!]?.text} />
              </li>
            ))}
          </ol>
        </PopoverContent>
      </Popover>
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
      {text && <p className="text-zinc-700 dark:text-zinc-300">{excerpt(text)}</p>}
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

function excerpt(text: string): string {
  return text.length > EXCERPT_LENGTH ? `${text.slice(0, EXCERPT_LENGTH).trimEnd()}…` : text;
}
