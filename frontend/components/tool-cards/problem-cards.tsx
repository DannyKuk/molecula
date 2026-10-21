import { useMessages } from "@/lib/messages";
import type { DrugNotSupported } from "@/lib/tool-cards";

/** Names outside the supported drugs, with the closest supported names as plain text. */
export function NotSupportedCard({ drugs }: { drugs: DrugNotSupported[] }) {
  const t = useMessages();
  return (
    <ul className="flex flex-col gap-2">
      {drugs.map((drug) => (
        <li key={drug.query}>
          <p>{t.cards.notInData(drug.query)}</p>
          {drug.suggestions.length > 0 && (
            <p className="mt-1 text-muted-foreground">
              {t.cards.closestNames(drug.suggestions.map(suggestionName).join(", "))}
            </p>
          )}
        </li>
      ))}
    </ul>
  );
}

/** "Tylenol (acetaminophen)", or just the name when the suggestion is the generic name. */
export function suggestionName(suggestion: { alias: string; name: string }): string {
  return suggestion.alias.toLowerCase() === suggestion.name.toLowerCase()
    ? suggestion.alias
    : `${suggestion.alias} (${suggestion.name})`;
}

/** A call the tool rejected before looking anything up, with one line per problem. */
export function InvalidCard({ errors }: { errors: string[] }) {
  const t = useMessages();
  return (
    <>
      <p>{t.cards.toolRejected}</p>
      <ul className="mt-1 list-disc pl-5 font-mono text-xs">
        {errors.map((error) => (
          <li key={error}>{error}</li>
        ))}
      </ul>
    </>
  );
}
