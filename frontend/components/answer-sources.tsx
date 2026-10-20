import type { Source } from "@/lib/chat";
import { isLabel, sourceLines } from "@/lib/citations";

const OPENFDA_URL = "https://open.fda.gov";

// openFDA's terms (https://open.fda.gov/terms/) ask for this credit, though they don't require it.
export function OpenFdaCredit() {
  return (
    <p className="text-xs text-muted-foreground">
      Data provided by the U.S. Food and Drug Administration (
      <a
        href={OPENFDA_URL}
        target="_blank"
        rel="noopener noreferrer"
        className="font-medium underline underline-offset-4"
      >
        openFDA
      </a>
      )
    </p>
  );
}

/**
 * Every source of the answer with its link, and the openFDA credit when it used label text, on
 * paper only, where the evidence panel doesn't print.
 */
export function PrintedSources({ sources }: { sources: Source[] }) {
  if (sources.length === 0) return null;
  return (
    <section aria-label="Sources" className="hidden text-xs print:block">
      <p className="font-medium">Sources</p>
      <ul>
        {sourceLines(sources).map((line) => (
          <li key={line} className="break-words">
            {line}
          </li>
        ))}
      </ul>
      {sources.some(isLabel) && <OpenFdaCredit />}
    </section>
  );
}
