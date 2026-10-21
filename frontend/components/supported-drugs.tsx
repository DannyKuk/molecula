"use client";

import { useEffect, useId, useState } from "react";

import { type Drug, type Resolution, resolveDrug, type Suggestion } from "@/lib/api";
import { byLetter, type DrugGroup, filterDrugs, namesToOffer } from "@/lib/drug-search";
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
  const groups = byLetter(matches);

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
      {!searched && <LetterBar groups={groups} />}
      <div id={listId} className="flex flex-col gap-4">
        {groups.map(({ letter, drugs: inGroup }) => (
          <section key={letter} id={letterId(letter)} aria-label={letter} className="scroll-mt-4">
            <h2 aria-hidden className="mb-1 font-mono text-xs text-signal">
              {letter}
            </h2>
            <ul className="border-b border-rule">
              {inGroup.map((drug) => (
                <li key={drug.cid} className="border-t border-rule">
                  <DrugRow drug={drug} onAsk={onAsk} />
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
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

const LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");

const letterId = (letter: string) => `drugs-${letter}`;

/** A to Z, each letter that starts a drug's name a link to its group. */
function LetterBar({ groups }: { groups: DrugGroup[] }) {
  const t = useMessages();
  const present = new Set(groups.map(({ letter }) => letter));
  return (
    <nav
      aria-label={t.drugs.letters}
      className="flex flex-wrap gap-0.5 font-mono text-xs text-ink-3"
    >
      {LETTERS.map((letter) =>
        present.has(letter) ? (
          <a
            key={letter}
            href={`#${letterId(letter)}`}
            className="rounded px-1.5 py-0.5 text-ink hover:bg-rule focus-visible:outline-2 focus-visible:outline-ink-3"
          >
            {letter}
          </a>
        ) : (
          <span key={letter} aria-hidden className="px-1.5 py-0.5">
            {letter}
          </span>
        ),
      )}
    </nav>
  );
}

function DrugRow({ drug, onAsk }: { drug: Drug; onAsk: (question: string) => void }) {
  const t = useMessages();
  const nameId = useId();
  const aliasesId = useId();
  const noStructureId = useId();
  const hasAliases = drug.aliases.length > 0;
  // The name alone labels the button; the aliases and a missing structure are read after it.
  const describedBy = [hasAliases && aliasesId, !drug.has_3d && noStructureId]
    .filter(Boolean)
    .join(" ");

  return (
    <button
      type="button"
      onClick={() => onAsk(t.drugs.question(drug.name))}
      aria-labelledby={nameId}
      aria-describedby={describedBy || undefined}
      className="group flex w-full items-baseline gap-3 px-1 py-2 text-left hover:bg-panel focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink-3 max-sm:flex-wrap max-sm:gap-y-0.5"
    >
      <span id={nameId} className="font-medium first-letter:uppercase sm:w-44 sm:shrink-0">
        {drug.name}
      </span>
      {hasAliases && (
        <span
          id={aliasesId}
          className="min-w-0 text-[13px] text-ink-3 max-sm:order-last max-sm:w-full sm:flex-1 sm:truncate"
        >
          {drug.aliases.join(", ")}
        </span>
      )}
      {!drug.has_3d && (
        <span id={noStructureId} className="text-xs text-ink-3">
          {t.drugs.noStructure}
        </span>
      )}
      <span
        aria-hidden
        className="ml-auto shrink-0 text-xs text-ink-3 opacity-0 group-hover:opacity-100 group-focus-visible:opacity-100 max-sm:hidden"
      >
        {t.drugs.askHint} ↵
      </span>
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
