import { useMessages } from "@/lib/messages";
import type { ResolvedDrug } from "@/lib/tool-cards";

import { SourceLink } from "./source-link";

/** The supported drug a name was found as, and the name it matched. */
export function DrugCard({ result }: { result: ResolvedDrug }) {
  const t = useMessages();
  return (
    <>
      <p>
        {t.quote(result.matched_alias)} {t.cards.matches[result.match_kind]}{" "}
        <span className="font-medium">{result.name}</span> (PubChem CID {result.cid}).
      </p>
      <p className="mt-2">
        <SourceLink href={result.source_url}>PubChem</SourceLink>
      </p>
    </>
  );
}
