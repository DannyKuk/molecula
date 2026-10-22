import type { Messages } from "./messages/en";

/** Who does a step of an answer: the chat model, the embedder or our own code. */
export type Who = "model" | "embedder" | "code";

export const WHO: Who[] = ["model", "embedder", "code"];

export type GuideStepId = keyof Messages["flow"]["guide"];

/** A guide step's words, from `flow.guide` in the dictionaries. `title` and `short` are shared
 * with an answer's Flow tab; `passes` is what the step hands to the next one. */
export type GuideWords = {
  title: string;
  short: string;
  text: string;
  aside?: string;
  passes?: string;
};

/**
 * One step from a question to a checked answer, as the guide explains it. `id` is the step's
 * anchor on `/how-it-answers` and its key in `flow.guide`; `onSteps` names what the Steps tab
 * shows for it, in the words of the progress lines.
 */
export type FlowStep = {
  id: GuideStepId;
  number: string;
  who: Who;
  call?: string;
  onSteps?: (t: Messages) => string;
};

export const EXAMPLE_QUESTION = "Does ibuprofen interact with warfarin?";

/** The steps of the example question, in the order the backend runs them: `guard/chat.py`, the
 * agent's `search_labels`, `rag/filters.py`, `rag/retriever.py`, `guard/canary.py` and
 * `guard/source_check.py`. */
export const FLOW_STEPS: FlowStep[] = [
  {
    id: "check-the-question",
    number: "1",
    who: "model",
    onSteps: (t) => t.progress.checking,
  },
  {
    id: "decide-what-to-look-up",
    number: "2",
    who: "model",
    call: 'search_labels(drug="ibuprofen", section="interactions")',
  },
  { id: "narrow-to-the-drug", number: "3", who: "code" },
  { id: "score-by-meaning", number: "4", who: "embedder" },
  {
    id: "boost-and-keep-five",
    number: "5",
    who: "code",
    onSteps: (t) => t.howItAnswers.rowsWithBars(t.progress.searchingLabel("ibuprofen")),
  },
  { id: "write-the-answer", number: "6", who: "model" },
  { id: "watch-for-a-leak", number: "6b", who: "code" },
  {
    id: "check-the-sources",
    number: "7",
    who: "model",
    onSteps: (t) => t.progress.checkingAnswer,
  },
];

/** The guide's step with anchor `id`. */
export function guideStep(id: GuideStepId): FlowStep {
  const step = FLOW_STEPS.find((candidate) => candidate.id === id);
  if (!step) throw new Error(`No guide step ${id}`);
  return step;
}

/** A passage a label search scored: its similarity, and whether it is in the section asked for. */
export type ScoredPassage = { section: string; similarity: number; inSection: boolean };

/** A passage in the order the boost gives, with its score and its place before and after. */
export type RankedPassage = ScoredPassage & { score: number; before: number; after: number };

/**
 * The passages ordered by similarity plus `boost` for those in the section asked for, with each
 * one's place by similarity alone and by the boosted score (1 is first). Ties keep the given
 * order, as the search's sort does.
 */
export function boostedRanking(passages: ScoredPassage[], boost: number): RankedPassage[] {
  const scored = passages.map((passage) => ({
    ...passage,
    score: passage.similarity + (passage.inSection ? boost : 0),
  }));
  const bySimilarity = [...scored].sort((a, b) => b.similarity - a.similarity);
  const byScore = [...scored].sort((a, b) => b.score - a.score);
  return byScore.map((passage, index) => ({
    ...passage,
    before: bySimilarity.indexOf(passage) + 1,
    after: index + 1,
  }));
}

export const SECTION_BOOST = 0.15;

/** The 5 passages the example's search kept on 2026-10-20 (offline, gpt-oss-20b and bge-m3),
 * in the order of their similarity. */
export const EXAMPLE_PASSAGES: ScoredPassage[] = [
  { section: "Nursing mothers", similarity: 0.64, inSection: false },
  { section: "Precautions", similarity: 0.64, inSection: false },
  { section: "Nursing mothers", similarity: 0.63, inSection: false },
  { section: "Drug interactions", similarity: 0.52, inSection: true },
  { section: "Drug and/or lab test interactions", similarity: 0.5, inSection: true },
];

/** How often the answering passage made the top 5 of 94 questions, by the size of the bonus
 * (`docs/evals/chat-model-filters-2026-10-12.md`): with the chat model's section guess, and
 * with the answer key's. The hard rule searches only the guessed section. */
export const BOOST_MEASUREMENTS: {
  bonus: number | "hard rule";
  guessed: number;
  alwaysRight: number;
  picked?: boolean;
}[] = [
  { bonus: 0, guessed: 0.85, alwaysRight: 0.85 },
  { bonus: 0.08, guessed: 0.9, alwaysRight: 0.95 },
  { bonus: 0.12, guessed: 0.91, alwaysRight: 0.96 },
  { bonus: 0.15, guessed: 0.91, alwaysRight: 0.97, picked: true },
  { bonus: 0.2, guessed: 0.9, alwaysRight: 0.97 },
  { bonus: "hard rule", guessed: 0.84, alwaysRight: 0.98 },
];
