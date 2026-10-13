import type { ResolvedDrug } from "@/lib/tool-cards";

import { SourceLink } from "./source-link";

const MATCHES: Record<ResolvedDrug["match_kind"], string> = {
  name: "is the generic name of",
  alias: "is a stored name for",
  brand: "is a brand of",
  pubchem: "is a PubChem synonym of",
};

/** The supported drug a name was found as, and the name it matched. */
export function DrugCard({ result }: { result: ResolvedDrug }) {
  return (
    <>
      <p>
        “{result.matched_alias}” {MATCHES[result.match_kind]}{" "}
        <span className="font-medium">{result.name}</span> (PubChem CID {result.cid}).
      </p>
      <p className="mt-2">
        <SourceLink href={result.source_url}>PubChem</SourceLink>
      </p>
    </>
  );
}
