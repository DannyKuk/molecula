import { citedRefs, labelDate, sectionName } from "@/lib/citations";
import type { LabelPassage, LabelPassages } from "@/lib/tool-cards";

import { SourceLink } from "./source-link";

/** What a label search looked for and every passage it found, each opening into its text;
 * the passages the answer cites are marked. */
export function LabelsCard({
  result,
  drug,
  section,
  answer,
}: {
  result: LabelPassages;
  drug: string | null;
  section: string | null;
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
        Searched for “{result.question}”{scope && ` in ${scope}`}.
      </p>
      {result.drugs_without_label.length > 0 && (
        <p className="mt-1">No US label for {result.drugs_without_label.join(", ")}.</p>
      )}
      {result.unsupported.length > 0 && (
        <p className="mt-1">
          Not supported: {result.unsupported.map((drug) => drug.query).join(", ")}.
        </p>
      )}
      {result.passages.length === 0 ? (
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

function Passage({ passage, cited }: { passage: LabelPassage; cited: boolean }) {
  return (
    <details>
      <summary className="cursor-pointer">
        <span className="text-muted-foreground tabular-nums">[{passage.ref}]</span>{" "}
        {passage.brand ?? passage.substance.toLowerCase()} · {sectionName(passage.section)}
        {passage.effective_time && (
          <span className="text-muted-foreground"> · {labelDate(passage.effective_time)}</span>
        )}
        {cited && (
          <span className="ml-1 rounded-full bg-zinc-100 px-2 py-0.5 text-xs dark:bg-zinc-800">
            cited
          </span>
        )}
      </summary>
      <p className="mt-1 rounded-md bg-zinc-50 p-2 text-xs leading-relaxed dark:bg-zinc-900">
        {passage.text}
      </p>
      <p className="mt-1 text-xs">
        <SourceLink href={passage.url}>Open the label on DailyMed</SourceLink>
      </p>
    </details>
  );
}
