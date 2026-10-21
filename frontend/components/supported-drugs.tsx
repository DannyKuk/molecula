"use client";

import { useEffect, useId, useState } from "react";

import { type Drug, type Resolution, resolveDrug, type Suggestion } from "@/lib/api";
import { filterDrugs, namesToOffer } from "@/lib/drug-search";
import { type Messages, useMessages } from "@/lib/messages";

/** How long typing has to pause before a name the list doesn't match is sent to the backend. */
const RESOLVE_DELAY_MS = 300;

type SupportedDrugsProps = {
  drugs: Drug[];
  onAsk: (question: string) => void;
};

export function SupportedDrugs({ drugs, onAsk }: SupportedDrugsProps) {
  const t = useMessages();
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
          {t.drugs.search}
        </label>
        <input
          id={searchId}
          type="search"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder={t.drugs.placeholder}
          autoComplete="off"
          spellCheck={false}
          aria-controls={listId}
          className="w-full rounded-lg border border-rule-2 bg-transparent px-3 py-2 text-base outline-none focus:border-ink-3 focus:ring-2 focus:ring-rule-2"
        />
      </div>
      <p role="status" className="text-sm text-ink-2">
        {resultSummary(t, query, matches.length, drugs.length, resolution?.status === "found")}
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
  const t = useMessages();
  return (
    <p className="text-sm text-ink-2">
      {t.drugs.didYouMean}{" "}
      {suggestions.map((suggestion, index) => (
        <span key={suggestion.alias}>
          {index > 0 && t.drugs.or}
          <button
            type="button"
            onClick={() => onPick(suggestion)}
            className="font-medium text-ink underline underline-offset-4 hover:text-ink focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3"
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
  const t = useMessages();
  const nameId = useId();
  const aliasesId = useId();
  const badgeId = useId();
  const hasAliases = drug.aliases.length > 0;
  // The name alone labels the button; aliases and badges are read after it as its description.
  const describedBy = [hasAliases && aliasesId, drug.has_3d && badgeId].filter(Boolean).join(" ");

  return (
    <button
      type="button"
      onClick={() => onAsk(t.drugs.question(drug.name))}
      aria-labelledby={nameId}
      aria-describedby={describedBy || undefined}
      className="flex h-full w-full flex-col items-start gap-1 rounded-lg border border-rule px-4 py-3 text-left hover:border-ink-3 hover:bg-card focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3"
    >
      <span className="flex w-full flex-wrap items-center justify-between gap-2">
        <span id={nameId} className="font-medium">
          {drug.name}
        </span>
        {drug.has_3d && (
          <span
            id={badgeId}
            className="rounded-full bg-panel px-2 py-0.5 text-xs font-medium text-ink"
          >
            {t.drugs.has3d}
          </span>
        )}
      </span>
      {hasAliases && (
        <span id={aliasesId} className="text-sm break-words text-ink-2">
          {drug.aliases.join(", ")}
        </span>
      )}
    </button>
  );
}

function resultSummary(
  t: Messages,
  query: string,
  matchCount: number,
  total: number,
  foundUnderAnotherName: boolean,
): string {
  const searched = query.trim();
  const supported = t.drugs.supported(total);
  if (!searched) return t.drugs.pickOne(supported);
  if (matchCount === 0 && foundUnderAnotherName) return t.drugs.underAnotherName(searched);
  if (matchCount === 0) return t.drugs.notSupported(searched, supported);
  return t.drugs.matches(matchCount, supported, searched);
}
