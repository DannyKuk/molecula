import type { ReactNode } from "react";

import type { Source } from "@/lib/chat";
import { citedRefs } from "@/lib/citations";

const SITE_NAMES: Record<string, string> = {
  pubchem: "PubChem",
  chembl: "ChEMBL",
  rcsb: "RCSB PDB",
};

/**
 * What sits under an answer once its sources are known: the labels it read when it cites none
 * of their passages, the PubChem, ChEMBL and RCSB pages its tools used, and openFDA's
 * disclaimer when it used label text.
 */
export function AnswerSources({
  answer,
  sources,
  disclaimer,
}: {
  answer: string;
  sources: Source[];
  disclaimer: string | null;
}) {
  const passages = sources.filter((source) => source.ref !== null);
  const cited = new Set(citedRefs(answer));
  const uncitedLabels = passages.some((source) => cited.has(source.ref!))
    ? []
    : uniqueByUrl(passages);
  const pages = uniqueByUrl(sources.filter((source) => source.ref === null));
  if (uncitedLabels.length === 0 && pages.length === 0 && !disclaimer) return null;

  return (
    <div className="flex flex-col gap-2 text-sm">
      {uncitedLabels.length > 0 && (
        <SourceLinks title="Based on">
          {uncitedLabels.map((source) => (
            <SourceLink key={source.url} href={source.url}>
              {source.name} label
            </SourceLink>
          ))}
        </SourceLinks>
      )}
      {pages.length > 0 && (
        <SourceLinks title={passages.length > 0 ? "Also from" : "From"}>
          {pages.map((source) => (
            <SourceLink key={source.url} href={source.url}>
              {SITE_NAMES[source.kind] ?? source.kind} · {source.name}
            </SourceLink>
          ))}
        </SourceLinks>
      )}
      {disclaimer && <p className="text-xs text-muted-foreground">{disclaimer}</p>}
    </div>
  );
}

function uniqueByUrl(sources: Source[]): Source[] {
  return [...new Map(sources.map((source) => [source.url, source])).values()];
}

function SourceLinks({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="text-muted-foreground">{title}</span>
      {children}
    </div>
  );
}

function SourceLink({ href, children }: { href: string; children: ReactNode }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="rounded-full border border-zinc-300 px-2 py-0.5 text-xs hover:bg-zinc-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-zinc-500 dark:border-zinc-700 dark:hover:bg-zinc-900"
    >
      {children}
    </a>
  );
}
