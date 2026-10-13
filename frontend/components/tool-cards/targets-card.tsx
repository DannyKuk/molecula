import type { DrugTargetList } from "@/lib/tool-cards";

import { ShowMore } from "./show-more";
import { SourceLink } from "./source-link";

// Protein complexes list dozens of genes (metformin's complex I has 50).
const SHOWN_GENES = 6;

/** The targets ChEMBL lists for a drug, each with its mechanism and its ChEMBL page. */
export function TargetsCard({ result }: { result: DrugTargetList }) {
  if (result.targets.length === 0) {
    return <p>ChEMBL lists no mechanism of action for {result.name}.</p>;
  }
  return (
    <ul className="flex flex-col gap-3">
      {result.targets.map((target) => (
        <li key={target.target_chembl_id}>
          <p className="font-medium">{target.name}</p>
          <p>{target.mechanism}</p>
          <p className="mt-1 flex flex-wrap items-center gap-x-1 text-xs text-muted-foreground">
            {[target.organism, target.target_type.toLowerCase()].filter(Boolean).join(" · ")}
            {target.gene_symbols.length > 0 && (
              <>
                <span>· genes:</span>
                <ShowMore
                  items={target.gene_symbols}
                  shown={SHOWN_GENES}
                  render={(gene) => (
                    <code key={gene} className="font-mono">
                      {gene}
                    </code>
                  )}
                />
              </>
            )}
          </p>
          <p className="mt-1">
            <SourceLink href={target.source_url}>ChEMBL</SourceLink>
          </p>
        </li>
      ))}
    </ul>
  );
}
