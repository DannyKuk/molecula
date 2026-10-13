import type { Suggestion } from "./api";
import { cardOf, type DrugNotSupported, type Step } from "./tool-cards";

/** A supported name offered for one the tools didn't find, and the question that asks with it. */
export type DidYouMean = { suggestion: Suggestion; question: string };

/** The suggestions the turn's tools returned for names they didn't find, once per question. */
export function didYouMeanOf(question: string, steps: Step[]): DidYouMean[] {
  const offers = new Map<string, DidYouMean>();
  for (const drug of notFound(steps)) {
    for (const suggestion of drug.suggestions) {
      const asked = withName(question, drug.query, suggestion.alias);
      if (!offers.has(asked)) offers.set(asked, { suggestion, question: asked });
    }
  }
  return [...offers.values()];
}

/** Names the tools didn't find: alone, in a comparison, or among the drugs of a label search. */
function notFound(steps: Step[]): DrugNotSupported[] {
  return steps.flatMap((step) => {
    const card = cardOf(step.tool);
    switch (card?.kind) {
      case "not_supported":
        return card.drugs;
      case "properties":
        return card.drugs.filter(
          (drug): drug is DrugNotSupported => drug.status === "not_supported",
        );
      case "labels":
        return card.result.unsupported;
      default:
        return [];
    }
  });
}

/**
 * The question with the name, in any case and wherever it stands as a whole word, replaced by
 * the suggested one. The model may have passed the tool another spelling than the question has;
 * then the question asks about the suggested name on its own.
 */
export function withName(question: string, name: string, suggested: string): string {
  const pattern = new RegExp(
    `(?<![\\p{L}\\p{N}])${escapeRegExp(name.trim())}(?![\\p{L}\\p{N}])`,
    "giu",
  );
  const asked = question.replace(pattern, () => suggested);
  return asked === question ? `What is ${suggested}?` : asked;
}

function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
