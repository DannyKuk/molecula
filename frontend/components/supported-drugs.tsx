"use client";

import { useId, useState } from "react";

import type { Drug } from "@/lib/api";
import { filterDrugs } from "@/lib/drug-search";

type SupportedDrugsProps = {
  drugs: Drug[];
  onAsk: (question: string) => void;
};

export function SupportedDrugs({ drugs, onAsk }: SupportedDrugsProps) {
  const [query, setQuery] = useState("");
  const searchId = useId();
  const listId = useId();
  const matches = filterDrugs(drugs, query);

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
        {resultSummary(query, matches.length, drugs.length)}
      </p>
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

function resultSummary(query: string, matchCount: number, total: number): string {
  const searched = query.trim();
  const supported = `${total} supported ${total === 1 ? "drug" : "drugs"}`;
  if (!searched) return `${supported}. Pick one to ask how it works.`;
  if (matchCount === 0) {
    return `“${searched}” is not supported. Molecula answers only about its ${supported}.`;
  }
  return `${matchCount} of ${supported} ${matchCount === 1 ? "matches" : "match"} “${searched}”.`;
}
