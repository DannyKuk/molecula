/** Who does a step of an answer: the chat model, the embedder or our own code. */
export type Who = "model" | "embedder" | "code";

export const WHO: Record<Who, { label: string; meaning: string }> = {
  model: {
    label: "Chat model",
    meaning:
      "gpt-oss-20b, the AI that reads and writes text. It is asked to decide or write something.",
  },
  embedder: {
    label: "Embedder",
    meaning:
      "bge-m3, a smaller AI that only turns text into numbers so meanings can be compared. It never writes.",
  },
  code: { label: "Code", meaning: "Our own rules. Same input, same result, every time." },
};

/**
 * One step from a question to a checked answer, as the guide explains it. `id` is the step's
 * anchor on `/how-it-answers`; `onSteps` names what the Steps tab shows for it; `passes` is what
 * the step hands to the next one.
 */
export type FlowStep = {
  id: string;
  number: string;
  title: string;
  who: Who;
  text: string;
  aside?: string;
  call?: string;
  onSteps?: string;
  passes?: string;
};

export const EXAMPLE_QUESTION = "Does ibuprofen interact with warfarin?";

/** The steps of the example question, in the order the backend runs them: `guard/chat.py`, the
 * agent's `search_labels`, `rag/filters.py`, `rag/retriever.py`, `guard/canary.py` and
 * `guard/source_check.py`. */
export const FLOW_STEPS: FlowStep[] = [
  {
    id: "check-the-question",
    number: "1",
    title: "Check the question",
    who: "model",
    text: "A short separate call sorts the message: a normal medicine question, a possible overdose (the answer then starts with emergency help), or something Molecula refuses, which gets a fixed answer. Only normal questions and overdose questions go on.",
    aside:
      "Online, Jev does this: a small model that only answers yes/no questions. Offline, as in this run, the chat model does it.",
    onSteps: "Checking the question",
    passes: "ok, a normal question",
  },
  {
    id: "decide-what-to-look-up",
    number: "2",
    title: "Decide what to look up",
    who: "model",
    text: "The chat model hasn't seen any label text yet. It decides to search the labels and fills in the search: which drug, and which part of the label it expects the answer in.",
    call: 'search_labels(drug="ibuprofen", section="interactions")',
    aside:
      "The part of the label is a guess made before the search. For a question about two or more drugs the chat model names no drug, and one more small call reads the drugs and the parts of the label from the question instead (Jev online, the chat model offline).",
    passes: "drug: ibuprofen · section: interactions",
  },
  {
    id: "narrow-to-the-drug",
    number: "3",
    title: "Narrow the search to the drug",
    who: "code",
    text: "The code looks the drug name up in our store, so “Gleevec” becomes imatinib, and only that drug's labels are searched (here, 2 ibuprofen labels). A section name that doesn't exist is dropped.",
    aside: "Two drugs are searched one by one, and each keeps its own top 5.",
    passes: "ibuprofen's labels, cut into passages and tagged by section",
  },
  {
    id: "score-by-meaning",
    number: "4",
    title: "Score the passages by meaning",
    who: "embedder",
    text: "The embedder turns the question into numbers and compares it with every ibuprofen passage. Each passage gets a similarity, about 0 for unrelated and 1 for the same meaning. Two lists are taken: the 5 closest passages in the interactions section and the 5 closest in the whole label, up to 10 candidates together.",
    aside: "Similarity means “sounds like the question”. It doesn't mean “is the right answer”.",
    passes: "up to 10 candidates, each with a similarity",
  },
  {
    id: "boost-and-keep-five",
    number: "5",
    title: "Add the +0.15 and keep the top 5",
    who: "code",
    text: "Each passage from the section guessed in step 2 gets +0.15 added to its score. Then the code sorts by the new score, keeps the top 5 and numbers them [1] to [5]. Plain arithmetic: no AI is asked anything here.",
    onSteps: "Searching the ibuprofen label, the rows with their bars",
    passes: "5 passages, numbered [1] to [5]",
  },
  {
    id: "write-the-answer",
    number: "6",
    title: "Write the answer",
    who: "model",
    text: "The chat model reads the 5 passages and writes the answer. Every fact gets the number of the passage it came from, like [3].",
    passes: "the answer with its [n] citations",
  },
  {
    id: "watch-for-a-leak",
    number: "6b",
    title: "Watch for a leaked system prompt",
    who: "code",
    text: "While the answer streams out, the code looks for a hidden marker placed in the system prompt (the canary). If it shows up, the answer is replaced with a fixed one before the marker reaches you.",
    passes: "the finished answer",
  },
  {
    id: "check-the-sources",
    number: "7",
    title: "Check the answer against the sources",
    who: "model",
    text: "A separate call compares each claim in the answer with the passage it cites, and marks whether the passage really says that.",
    onSteps: "Checking the answer against the sources",
  },
];

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
 * with the answer key's. */
export const BOOST_MEASUREMENTS = [
  { bonus: "None", guessed: 0.85, alwaysRight: 0.85 },
  { bonus: "+0.08", guessed: 0.9, alwaysRight: 0.95 },
  { bonus: "+0.12", guessed: 0.91, alwaysRight: 0.96 },
  { bonus: "+0.15", guessed: 0.91, alwaysRight: 0.97, picked: true },
  { bonus: "+0.20", guessed: 0.9, alwaysRight: 0.97 },
  { bonus: "Search only the guessed section", guessed: 0.84, alwaysRight: 0.98 },
];
