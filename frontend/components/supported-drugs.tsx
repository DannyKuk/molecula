"use client";

import { useEffect, useId, useState } from "react";

import { type Drug, type Resolution, resolveDrug, type Suggestion } from "@/lib/api";
import { filterDrugs, namesToOffer } from "@/lib/drug-search";

/** How long typing has to pause before a name the list doesn't match is sent to the backend. */
const RESOLVE_DELAY_MS = 300;

type SupportedDrugsProps = {
  drugs: Drug[];
  onAsk: (question: string) => void;
};

export function SupportedDrugs({ drugs, onAsk }: SupportedDrugsProps) {
  const [query, setQuery] = useState("");
  const searchId = useId();
  const listId = useId();
  const matches = filterDrugs(drugs, query);
  const searched = query.trim();
  const resolution = useResolution(matches.length === 0 ? searched : "");
  const offered = resolution ? namesToOffer(resolution) : [];

  return (
    <section className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <label htmlFor={searchId} className="text-sm font-medium">
          Search by name or brand
        </label>
        <input
          id={searchId}
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="e.g. Tylenol or imatinib"
          autoComplete="off"
          spellCheck={false}
          aria-controls={listId}
          className="w-full rounded-lg border border-zinc-300 bg-transparent px-3 py-2 text-base outline-none focus:border-zinc-500 focus:ring-2 focus:ring-zinc-300 dark:border-zinc-700 dark:focus:border-zinc-400 dark:focus:ring-zinc-700"
        />
      </div>
      <p role="status" className="text-sm text-zinc-600 dark:text-zinc-400">
        {resultSummary(query, matches.length, drugs.length, resolution?.status === "found")}
      </p>
      {offered.length > 0 && (
        <SuggestionLine suggestions={offered} onPick={(suggestion) => setQuery(suggestion.name)} />
      )}
      <ul id={listId} className="grid gap-2 sm:grid-cols-2">
        {matches.map((drug) => (
          <li key={drug.cid}>
            <DrugButton drug={drug} onAsk={onAsk} />
          </li>
        ))}
      </ul>
    </section>
  );
}

/** The backend's resolution of a name once typing has paused; null before that, or on failure. */
function useResolution(name: string): Resolution | null {
  const [resolved, setResolved] = useState<{ name: string; resolution: Resolution } | null>(null);

  useEffect(() => {
    if (!name) return;
    const controller = new AbortController();
    const timer = setTimeout(() => {
      resolveDrug(name, controller.signal)
        .then((resolution) => setResolved({ name, resolution }))
        // A failed lookup leaves the plain "not supported" message.
        .catch(() => {});
    }, RESOLVE_DELAY_MS);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [name]);

  return name && resolved?.name === name ? resolved.resolution : null;
}

function SuggestionLine({
  suggestions,
  onPick,
}: {
  suggestions: Suggestion[];
  onPick: (suggestion: Suggestion) => void;
}) {
  return (
    <p className="text-sm text-zinc-600 dark:text-zinc-400">
      Did you mean{" "}
      {suggestions.map((suggestion, index) => (
        <span key={suggestion.alias}>
          {index > 0 && " or "}
          <button
            type="button"
            onClick={() => onPick(suggestion)}
            className="font-medium text-zinc-900 underline underline-offset-4 hover:text-zinc-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 dark:text-zinc-100 dark:hover:text-zinc-300"
          >
            {suggestionLabel(suggestion)}
          </button>
        </span>
      ))}
      ?
    </p>
  );
}

function suggestionLabel({ alias, name }: Suggestion): string {
  return alias === name ? name : `${alias} (${name})`;
}

function DrugButton({ drug, onAsk }: { drug: Drug; onAsk: (question: string) => void }) {
  const nameId = useId();
  const aliasesId = useId();
  const badgeId = useId();
  const hasAliases = drug.aliases.length > 0;
  // The name alone labels the button; aliases and badges are read after it as its description.
  const describedBy = [hasAliases && aliasesId, drug.has_3d && badgeId].filter(Boolean).join(" ");

  return (
    <button
      type="button"
      onClick={() => onAsk(questionAbout(drug))}
      aria-labelledby={nameId}
      aria-describedby={describedBy || undefined}
      className="flex h-full w-full flex-col items-start gap-1 rounded-lg border border-zinc-200 px-4 py-3 text-left hover:border-zinc-400 hover:bg-zinc-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 dark:border-zinc-800 dark:hover:border-zinc-600 dark:hover:bg-zinc-900"
    >
      <span className="flex w-full flex-wrap items-center justify-between gap-2">
        <span id={nameId} className="font-medium">
          {drug.name}
        </span>
        {drug.has_3d && (
          <span
            id={badgeId}
            className="rounded-full bg-sky-100 px-2 py-0.5 text-xs font-medium text-sky-800 dark:bg-sky-950 dark:text-sky-300"
          >
            3D structure
          </span>
        )}
      </span>
      {hasAliases && (
        <span id={aliasesId} className="text-sm break-words text-zinc-600 dark:text-zinc-400">
          {drug.aliases.join(", ")}
        </span>
      )}
    </button>
  );
}

function questionAbout(drug: Drug): string {
  return `How does ${drug.name} work?`;
}

function resultSummary(
  query: string,
  matchCount: number,
  total: number,
  foundUnderAnotherName: boolean,
): string {
  const searched = query.trim();
  const supported = `${total} supported ${total === 1 ? "drug" : "drugs"}`;
  if (!searched) return `${supported}. Pick one to ask how it works.`;
  if (matchCount === 0 && foundUnderAnotherName) {
    return `“${searched}” is supported under another name.`;
  }
  if (matchCount === 0) {
    return `“${searched}” is not supported. Molecula answers only about its ${supported}.`;
  }
  return `${matchCount} of ${supported} ${matchCount === 1 ? "matches" : "match"} “${searched}”.`;
}
