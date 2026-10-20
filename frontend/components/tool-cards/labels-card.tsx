import { cn } from "cn";
import type { ReactNode } from "react";

import { citedRefs, labelDate, sectionName } from "@/lib/citations";
import type {
  Candidate,
  LabelFilter,
  LabelPassage,
  LabelPassages,
  RetrievalTrace,
} from "@/lib/tool-cards";

import { SourceLink } from "./source-link";

/** What a label search looked for and every passage it found, each opening into its text;
 * the passages the answer cites are marked. With the search's trace it also shows what the search
 * was narrowed to and how it ranked every passage it scored (#41). */
export function LabelsCard({
  result,
  drug,
  section,
  trace,
  answer,
}: {
  result: LabelPassages;
  drug: string | null;
  section: string | null;
  trace: RetrievalTrace | null;
  answer: string;
}) {
  const cited = new Set(citedRefs(answer));
  const scope = [
    drug && `the ${drug} label`,
    section && `${sectionName(section).toLowerCase()} sections`,
  ]
    .filter(Boolean)
    .join(", ");
  return (
    <>
      <p className="text-muted-foreground">
        Searched for “{trace?.question ?? result.question}”{scope && ` in ${scope}`}.
      </p>
      {result.drugs_without_label.length > 0 && (
        <p className="mt-1">No US label for {result.drugs_without_label.join(", ")}.</p>
      )}
      {result.unsupported.length > 0 && (
        <p className="mt-1">
          Not supported: {result.unsupported.map((drug) => drug.query).join(", ")}.
        </p>
      )}
      {trace ? (
        <SearchTrace trace={trace} passages={result.passages} cited={cited} />
      ) : result.passages.length === 0 ? (
        <p className="mt-2">No passage matched the question.</p>
      ) : (
        <ul className="mt-2 flex flex-col gap-1.5">
          {result.passages.map((passage) => (
            <li key={passage.ref}>
              <Passage passage={passage} cited={cited.has(passage.ref)} />
            </li>
          ))}
        </ul>
      )}
    </>
  );
}

const RANKING = {
  dense: "Embeddings: closest in meaning",
  bm25: "Keywords (BM25)",
  hybrid: "Keywords and embeddings, merged by rank",
};

function SearchTrace({
  trace,
  passages,
  cited,
}: {
  trace: RetrievalTrace;
  passages: LabelPassage[];
  cited: Set<number>;
}) {
  const refs = new Map(passages.map((passage) => [passage.id, passage.ref]));
  const kept = trace.candidates.filter((candidate) => candidate.kept);
  return (
    <>
      <dl className="mt-2 grid grid-cols-[5.5rem_1fr] gap-x-3 gap-y-1.5 text-[12.5px]">
        <Fact term="Translation">
          {trace.translation.length > 0 ? (
            trace.translation.map((step) => <p key={step.step}>{step.output}</p>)
          ) : (
            <Skipped>searched with the question as written</Skipped>
          )}
        </Fact>
        <Fact term="Drugs">
          <Drugs filter={trace.filter} />
          <p className="mt-0.5 text-xs text-ink-3">
            {trace.filter === null
              ? "No drug named, so every label was searched."
              : trace.filter_source === "agent"
                ? "Named by the chat model when it called the search."
                : "Read from the question by the label filter."}
          </p>
          {trace.filter?.extraction_error && (
            <p className="mt-0.5 text-xs text-ink-3">
              The label filter gave no answer: {trace.filter.extraction_error}
            </p>
          )}
        </Fact>
        <Fact term="Sections">
          <Sections filter={trace.filter} widened={trace.widened.length > 0} />
        </Fact>
        {trace.filter?.product_type && (
          <Fact term="Product">
            {trace.filter.product_type === "otc" ? "Over the counter" : "Prescription"} labels
          </Fact>
        )}
        <Fact term="Ranked by">{RANKING[trace.mode]}</Fact>
      </dl>
      {trace.candidates.length === 0 ? (
        <p className="mt-2">No passage matched the question.</p>
      ) : (
        <ol aria-label="Passages by rank" className="mt-2 flex flex-col gap-0.5">
          {trace.candidates.map((candidate, index) => {
            const ref = refs.get(candidate.id);
            return (
              <li key={candidate.id}>
                <Ranked
                  candidate={candidate}
                  rank={candidate.kept ? index + 1 : null}
                  ref_={ref}
                  cited={ref !== undefined && cited.has(ref)}
                  hybrid={trace.mode !== "dense"}
                  minScore={trace.min_score}
                  boost={
                    trace.mode === "dense" && candidate.in_section_groups
                      ? trace.section_group_boost
                      : 0
                  }
                />
              </li>
            );
          })}
        </ol>
      )}
      <p className="mt-1.5 text-xs text-ink-3">
        {kept.length < trace.candidates.length
          ? `${trace.candidates.length - kept.length} dropped for a similarity below ${trace.min_score.toFixed(2)}.`
          : `Nothing scored below the minimum similarity of ${trace.min_score.toFixed(2)}.`}
        {trace.mode === "dense"
          ? kept.some((candidate) => candidate.in_section_groups) &&
            ` A passage from the section the search asked for counts ${trace.section_group_boost.toFixed(2)} higher in the ranking, the light end of its bar.`
          : " The order comes from each passage's place in both rankings, not from the similarity."}
      </p>
    </>
  );
}

function Drugs({ filter }: { filter: LabelFilter | null }) {
  if (!filter || (filter.drugs.length === 0 && filter.unsupported.length === 0)) {
    return <p>Any</p>;
  }
  return (
    <ul className="flex flex-wrap gap-1">
      {filter.drugs.map((drug) => (
        <li key={drug.name} className={PILL}>
          {drug.name}
          {drug.name.toLowerCase() !== drug.generic && (
            <>
              <span className="text-ink-3"> → </span>
              {drug.generic}
            </>
          )}
          <span className="text-xs text-ink-3">
            {" · "}
            {drug.set_ids.length} {drug.set_ids.length === 1 ? "label" : "labels"}
            {drug.narrowed && ", narrowed"}
          </span>
        </li>
      ))}
      {filter.unsupported.map((name) => (
        <li key={name.query} className={cn(PILL, "border-dashed")}>
          {name.query} <span className="text-xs text-ink-3">not supported</span>
        </li>
      ))}
    </ul>
  );
}

function Sections({ filter, widened }: { filter: LabelFilter | null; widened: boolean }) {
  const groups = filter?.section_groups ?? [];
  return (
    <>
      {groups.length > 0 ? (
        <p>
          {groups.map(sectionName).join(", ")}{" "}
          <span className="text-xs text-ink-3">moved to the top, the rest still searched</span>
        </p>
      ) : (
        <p>The whole label</p>
      )}
      {widened && (
        <p className="mt-0.5 text-xs text-ink-3">
          The narrowed labels have none of these, so every label of the drug was searched.
        </p>
      )}
      {filter && filter.ignored_section_groups.length > 0 && (
        <p className="mt-0.5 text-xs text-ink-3">
          Left out, not a label section: {filter.ignored_section_groups.join(", ")}
        </p>
      )}
    </>
  );
}

function Ranked({
  candidate,
  rank,
  ref_,
  cited,
  hybrid,
  minScore,
  boost,
}: {
  candidate: Candidate;
  rank: number | null;
  ref_: number | undefined;
  cited: boolean;
  hybrid: boolean;
  minScore: number;
  boost: number;
}) {
  const similarity = Math.max(0, candidate.score);
  return (
    <details
      data-cited={cited || undefined}
      className={cn("rounded-md", cited && "bg-signal-soft", !candidate.kept && "opacity-60")}
    >
      <summary className="grid cursor-pointer grid-cols-[1.25rem_1fr_6rem_2rem] items-center gap-2 px-1.5 py-1 text-[12.5px]">
        <span className="font-mono text-[11px] text-ink-3">{rank ?? "–"}</span>
        <span className="min-w-0">
          <span className="block truncate">
            {sectionName(candidate.section)}
            <span className="text-xs text-ink-3">
              {" · "}
              {candidate.brand ?? candidate.substance.toLowerCase()}
            </span>
          </span>
          <span className="flex flex-wrap gap-x-2 font-mono text-[10.5px] text-ink-3">
            {boost > 0 && (
              <span className="text-signal">+{boost.toFixed(2)} section asked for</span>
            )}
            {hybrid && (
              <span>
                embeddings #{candidate.dense_rank ?? "–"} · keywords #{candidate.bm25_rank ?? "–"}
              </span>
            )}
            {!candidate.kept && <span>dropped, below {minScore.toFixed(2)}</span>}
          </span>
        </span>
        <span className="flex items-center gap-1.5" title="Similarity to the question">
          <span className="flex h-1.5 flex-1 overflow-hidden rounded-full bg-rule">
            <span
              className={cn("h-full", cited ? "bg-signal" : "bg-ink-3")}
              style={{ width: `${Math.min(1, similarity) * 100}%` }}
            />
            {boost > 0 && (
              <span
                aria-hidden
                className="h-full bg-signal/45"
                style={{ width: `${Math.min(1 - Math.min(1, similarity), boost) * 100}%` }}
              />
            )}
          </span>
          <span className="font-mono text-[11px] text-ink-2">{candidate.score.toFixed(2)}</span>
        </span>
        <span className="text-right font-mono text-[11px]">
          {ref_ !== undefined && (
            <span className={cited ? "font-semibold text-signal" : "text-ink-3"}>[{ref_}]</span>
          )}
          {cited && <span className="sr-only"> cited</span>}
        </span>
      </summary>
      <p className="mx-1.5 mt-1 rounded-r-md border-l-2 border-signal bg-card p-2 text-xs leading-relaxed">
        {candidate.text}
      </p>
      <p className="mx-1.5 mt-1 mb-1.5 text-xs">
        <SourceLink href={candidate.url}>Open the label on DailyMed</SourceLink>
      </p>
    </details>
  );
}

const PILL = "rounded-md border border-rule-2 bg-page px-1.5 py-px";

function Fact({ term, children }: { term: string; children: ReactNode }) {
  return (
    <>
      <dt className="text-ink-3">{term}</dt>
      <dd className="min-w-0">{children}</dd>
    </>
  );
}

function Skipped({ children }: { children: ReactNode }) {
  return (
    <p>
      <span className="rounded-full border border-rule-2 px-1.5 font-mono text-[10px] tracking-wider text-ink-3 uppercase">
        Skipped
      </span>{" "}
      <span className="text-xs text-ink-3">{children}</span>
    </p>
  );
}

function Passage({ passage, cited }: { passage: LabelPassage; cited: boolean }) {
  return (
    <details>
      <summary className="cursor-pointer">
        <span className="font-mono text-xs font-semibold text-signal">[{passage.ref}]</span>{" "}
        {passage.brand ?? passage.substance.toLowerCase()} · {sectionName(passage.section)}
        {passage.effective_time && (
          <span className="text-muted-foreground"> · {labelDate(passage.effective_time)}</span>
        )}
        {cited && <span className="ml-1 rounded-full bg-panel px-2 py-0.5 text-xs">cited</span>}
      </summary>
      <p className="mt-1 rounded-r-md border-l-2 border-signal bg-card p-2 text-xs leading-relaxed">
        {passage.text}
      </p>
      <p className="mt-1 text-xs">
        <SourceLink href={passage.url}>Open the label on DailyMed</SourceLink>
      </p>
    </details>
  );
}
