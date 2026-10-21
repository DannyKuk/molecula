import {
  boostedRanking,
  type FlowStep,
  guideStep,
  type RankedPassage,
  type Who,
} from "./answer-flow";
import type { InputCategory } from "./api";
import type { Turn } from "./chat-turn";
import { citedRefs, sectionName } from "./citations";
import { CHECKING_ANSWER, checkSummary } from "./source-check";
import { CATEGORY_LABELS } from "./stats";
import {
  type Card,
  cardOf,
  type DrugComplex,
  type DrugNotSupported,
  type DrugProperties,
  type DrugTargetList,
  type LabelPassages,
  type RetrievalTrace,
  type Step,
  structureSubtitle,
  type StructureTarget,
  structureTitle,
  type ToolRun,
} from "./tool-cards";

/**
 * Where a step of an answer stands. `pending` is only an intermediate state of the builder: the
 * steps that haven't concluded become `running`, `waiting`, `stopped`, `failed` or `not_reached`
 * from the turn's state.
 */
export type TurnStepState =
  "done" | "skipped" | "running" | "waiting" | "stopped" | "failed" | "not_reached";

/**
 * One step the answer ran, as its Flow tab shows it. `number` counts the answer's own steps from
 * 1, so it differs from the guide's numbering when the answer took another path than the guide's
 * example. `guide` is the guide step's anchor on `/how-it-answers`, null for a step the guide
 * doesn't follow; `whoLabel` names who did it when
 * the event doesn't say which of two models it was. `outcome` is what happened in this answer,
 * `call` the tool call as the chat model wrote it and `ranking` the passages a dense search kept,
 * ordered as the section bonus left them.
 */
export type TurnStep = {
  key: string;
  guide: string | null;
  number: string;
  title: string;
  who: Who;
  whoLabel?: string;
  line: string;
  state: TurnStepState;
  outcome?: string;
  call?: string;
  ranking?: { passages: RankedPassage[]; boost: number };
};

/** A group of steps: one lookup, with the progress line that announced it, or the check and
 * the answer, which have no title. */
export type TurnFlowPart = { title: string | null; steps: TurnStep[] };

type Draft = Omit<TurnStep, "state" | "number"> & { state: TurnStepState | "pending" };

type DraftPart = { title: string | null; steps: Draft[] };

// The input check and the label filter's extra call run on Jev online and on the chat model
// offline, and no chat event says which (`open_input_check` and `open_filter_extractor` in
// `backend/src/molecula/main.py`).
const EITHER_MODEL = "Jev or chat model";

const REFUSED: InputCategory[] = [
  "personal_medical_advice",
  "lethal_dose",
  "synthesis_or_misuse",
  "prompt_injection",
  "off_topic",
];

type ToolStep = Step & { tool: ToolRun };

/**
 * The steps an answer ran, in order, from its own events: the input check, each lookup the chat
 * model asked for, the answer, the canary watch and the source check. A label search shows the
 * guide's call, filter, scoring and ranking steps from its arguments, its result and its
 * `retrieval_trace`; any other tool shows the call and the store lookup, and a structure lookup
 * the 3D view as well. Steps that haven't concluded take their state from the
 * turn: the first one running, stopped or failed, the others waiting or not reached.
 */
export function turnFlow(turn: Turn): TurnFlowPart[] {
  const tools = turn.steps.filter((step): step is ToolStep => step.tool !== undefined);
  const searches = tools.filter((step) => step.tool.name === "search_labels");
  const fixed = isFixedAnswer(turn, tools);
  // Only an ended answer shows that no lookup is coming: a live one may still call a tool, and an
  // overdose answer's emergency line streams before the chat model has decided anything.
  const answered =
    turn.state === "done" ||
    ((turn.state === "stopped" || turn.state === "failed") && turn.answer !== "");

  const parts: DraftPart[] = [{ title: null, steps: [checkStep(turn, tools, fixed)] }];
  if (tools.length === 0) {
    parts.push({ title: null, steps: noLookupSteps(fixed, answered) });
  }
  for (const step of tools) {
    if (step.tool.name === "search_labels") {
      const index = searches.indexOf(step);
      const title =
        searches.length > 1
          ? `Search ${index + 1} of ${searches.length} · ${step.text}`
          : step.text;
      parts.push({ title, steps: searchSteps(step.tool, String(index)) });
    } else {
      parts.push({ title: step.text, steps: lookupSteps(step.tool) });
    }
  }
  parts.push({ title: null, steps: answerSteps(turn, fixed) });
  return settle(parts, turn);
}

/**
 * Whether the input check refused the question and Molecula gave a fixed answer. Turns saved
 * before the category was kept have none: a finished one that ran no lookup, no source check
 * and wasn't withdrawn got a fixed answer.
 */
function isFixedAnswer(turn: Turn, tools: ToolStep[]): boolean {
  if (turn.category) return REFUSED.includes(turn.category);
  return (
    turn.state === "done" &&
    !turn.replaced &&
    tools.length === 0 &&
    turn.sourceCheck === null &&
    !turn.steps.some((step) => step.text === CHECKING_ANSWER)
  );
}

function fromGuide(id: string, key: string, changes: Partial<Draft> = {}): Draft {
  const step: FlowStep = guideStep(id);
  return {
    key,
    guide: step.id,
    title: step.title,
    who: step.who,
    line: step.short,
    state: "pending",
    ...changes,
  };
}

function checkStep(turn: Turn, tools: ToolStep[], fixed: boolean): Draft {
  const step = fromGuide("check-the-question", "check", { whoLabel: EITHER_MODEL });
  const passed = tools.length > 0 || turn.answer !== "" || turn.state === "done";
  if (!passed) return step;
  return { ...step, state: "done", outcome: checkOutcome(turn.category, fixed) };
}

function checkOutcome(category: InputCategory | undefined, fixed: boolean): string {
  if (category === "overdose_emergency") {
    return "Sorted as a possible overdose, so the answer starts with emergency help.";
  }
  if (category && fixed) {
    return `Sorted as ${CATEGORY_LABELS[category].toLowerCase()}, so Molecula gave a fixed answer and nothing else ran.`;
  }
  if (fixed) return "Molecula gave a fixed answer, so nothing else ran.";
  if (category === "ok") return "Sorted as a medicine question, so it went on.";
  return "Passed, so it went on.";
}

/** The lookup steps of an answer that looked nothing up. */
function noLookupSteps(fixed: boolean, answered: boolean): Draft[] {
  const decide = fromGuide("decide-what-to-look-up", "decide");
  if (!fixed && !answered) return [decide];
  const lookups = [
    fromGuide("narrow-to-the-drug", "narrow", { state: "skipped" }),
    fromGuide("score-by-meaning", "score", { state: "skipped" }),
    fromGuide("boost-and-keep-five", "boost", { state: "skipped" }),
  ];
  return [
    {
      ...decide,
      state: "skipped",
      outcome: fixed ? undefined : "The chat model answered without looking anything up.",
    },
    ...lookups,
  ];
}

/** The call as the chat model wrote it, without the arguments it left empty. A label search
 * leaves out its question, which the search step shows, unless it has no other argument. */
export function callText(tool: ToolRun): string {
  const entries = Object.entries(tool.args).filter(([, value]) => value !== null);
  const shown =
    tool.name === "search_labels" && entries.length > 1
      ? entries.filter(([name]) => name !== "question")
      : entries;
  const args = shown.map(([name, value]) => `${name}=${JSON.stringify(value)}`);
  return `${tool.name}(${args.join(", ")})`;
}

function lookupSteps(tool: ToolRun): Draft[] {
  const key = tool.id;
  const decide = fromGuide("decide-what-to-look-up", `${key}:decide`, {
    state: "done",
    call: callText(tool),
  });
  const lookup: Draft = {
    key: `${key}:lookup`,
    guide: null,
    title: "Look it up in the store",
    who: "code",
    line: "Code reads the answer from Molecula's own store. No AI is asked.",
    state: "pending",
  };
  const card = cardOf(tool);
  const outcome = lookupOutcome(tool, card);
  const shown =
    card?.kind === "complex" || card?.kind === "no_complex" ? [showIn3d(card, key)] : [];
  return [decide, outcome ? { ...lookup, state: "done", outcome } : lookup, ...shown];
}

function lookupOutcome(tool: ToolRun, card: Card | null): string | null {
  if (card === null) return tool.result === undefined ? null : "Done.";
  switch (card.kind) {
    case "pending":
      return null;
    case "invalid":
      return `Rejected and sent back to the chat model as an error: ${card.errors.join("; ")}`;
    case "not_supported":
      return notInStore(card.drugs);
    case "drug":
      return `“${card.result.query}” is ${card.result.name} in the store.`;
    case "properties":
      return propertiesOutcome(card.drugs);
    case "targets":
      return targetsOutcome(card.result);
    case "complex":
      return `A reviewed structure: ${structureTitle(complexTarget(card.result))}, ${structureSubtitle(complexTarget(card.result))}.`;
    case "no_complex":
      return `No reviewed structure of ${card.result.name} with its target.`;
    case "labels":
      return `${count(card.result.passages.length, "passage")} found.`;
  }
}

function notInStore(drugs: DrugNotSupported[]): string {
  return `Not in the store: ${drugs.map((drug) => drug.query).join(", ")}.`;
}

function propertiesOutcome(drugs: (DrugProperties | DrugNotSupported)[]): string {
  const found = drugs.filter((drug): drug is DrugProperties => drug.status === "found");
  const missing = drugs.filter((drug): drug is DrugNotSupported => drug.status !== "found");
  const parts =
    found.length === 1
      ? [
          `${found[0].compound.name}: ${found[0].compound.formula}, ${found[0].compound.molecular_weight} g/mol.`,
        ]
      : found.length > 1
        ? [`The properties of ${found.map((drug) => drug.compound.name).join(", ")}, side by side.`]
        : [];
  if (missing.length > 0) parts.push(notInStore(missing));
  return parts.join(" ");
}

function targetsOutcome(result: DrugTargetList): string {
  const names = result.targets.map((target) => target.name);
  if (names.length === 0) return `ChEMBL lists no mechanism for ${result.name}.`;
  const shown = names.slice(0, 3).join(", ");
  const more = names.length > 3 ? ` and ${names.length - 3} more` : "";
  return `${count(names.length, "target")}: ${shown}${more}.`;
}

function complexTarget(complex: DrugComplex): StructureTarget {
  return { cid: complex.cid, name: complex.name, complex };
}

/** What the 3D panel does with a structure the answer looked up: it loads it from the backend,
 * which reads it from the store (`get_drug_complex` and `get_drug_structure` in `api/drugs.py`),
 * and the browser draws it. */
function showIn3d(card: Extract<Card, { kind: "complex" | "no_complex" }>, key: string): Draft {
  return {
    key: `${key}:3d`,
    guide: null,
    title: "Show it in 3D",
    who: "code",
    line: "The 3D tab loads the structure from Molecula's own store and your browser draws it. No AI is asked and nothing is fetched from outside.",
    state: "done",
    outcome:
      card.kind === "complex"
        ? `The 3D tab shows ${structureTitle(complexTarget(card.result))}.`
        : "The 3D tab shows the molecule alone, from its stored 3D shape.",
  };
}

function searchSteps(tool: ToolRun, index: string): Draft[] {
  const key = `${tool.id || index}`;
  const decide = fromGuide("decide-what-to-look-up", `${key}:decide`, {
    state: "done",
    call: callText(tool),
  });
  const trace = tool.trace ?? null;
  const extracted =
    trace?.filter_source === "model"
      ? [
          fromGuide("decide-what-to-look-up", `${key}:extract`, {
            title: "Read the drugs from the question",
            whoLabel: EITHER_MODEL,
            line: "The call named no drug, so one more small call reads the drugs and the parts of the label from the question.",
            state: "done",
            outcome: trace.filter
              ? filterText(trace)
              : "No drug found, so every label was searched.",
          }),
        ]
      : [];
  return [decide, ...extracted, ...searchedSteps(tool, trace, key)];
}

/** The filter, scoring and ranking steps of one label search. */
function searchedSteps(tool: ToolRun, trace: RetrievalTrace | null, key: string): Draft[] {
  const narrow = fromGuide("narrow-to-the-drug", `${key}:narrow`);
  const score = fromGuide("score-by-meaning", `${key}:score`);
  const boost = fromGuide("boost-and-keep-five", `${key}:boost`);
  const card = cardOf(tool);
  if (card === null || card.kind === "pending") return [narrow, score, boost];
  const skipped = [score, boost].map((step): Draft => ({ ...step, state: "skipped" }));
  if (card.kind === "invalid") {
    const outcome = `Rejected and sent back to the chat model as an error, so nothing was searched: ${card.errors.join("; ")}`;
    return [{ ...narrow, state: "done", outcome }, ...skipped];
  }
  if (card.kind === "not_supported") {
    const names = card.drugs.map((drug) => drug.query).join(", ");
    const outcome = `None of the names is in the store (${names}), so nothing was searched.`;
    return [{ ...narrow, state: "done", outcome }, ...skipped];
  }
  if (card.kind !== "labels") return [narrow, score, boost];
  const result = card.result;
  if (!trace) return untracedSteps(result, narrow, score, boost);
  const several = searchedDrugs(trace) > 1;
  const narrowed: Draft = {
    ...narrow,
    ...(several && {
      title: "Narrow the search to the drugs",
      line: "Code looks the drugs up in the store and searches only their labels, one drug at a time.",
    }),
    state: "done",
    outcome: narrowText(trace, result),
  };
  if (trace.candidates.length === 0) {
    return [
      narrowed,
      { ...score, state: "skipped", outcome: "No passage to score." },
      { ...boost, state: "skipped" },
    ];
  }
  const ranked = boostStep(boost, trace);
  return [
    narrowed,
    scoreStep(score, trace),
    several && trace.mode === "dense"
      ? {
          ...ranked,
          line: "Code adds +0.15 to passages in the guessed section, sorts by the new score and keeps each drug's top 5. No AI is asked.",
        }
      : ranked,
  ];
}

function searchedDrugs(trace: RetrievalTrace): number {
  return trace.filter?.drugs.filter((drug) => drug.set_ids.length > 0).length ?? 0;
}

const UNRECORDED = "Not recorded: this search was saved before searches kept their details.";

function untracedSteps(result: LabelPassages, narrow: Draft, score: Draft, boost: Draft): Draft[] {
  const kept = result.passages.length;
  const refs = result.passages.map((passage) => passage.ref);
  const outcome =
    kept === 0
      ? "No passage matched the question."
      : `Kept ${count(kept, "passage")}, numbered ${refRange(refs)}.`;
  return [
    { ...narrow, state: "done", outcome: UNRECORDED },
    { ...score, state: "done", outcome: UNRECORDED },
    { ...boost, state: "done", outcome },
  ];
}

function filterText(trace: RetrievalTrace): string {
  const filter = trace.filter;
  if (!filter) return "No drug named, so every label was searched.";
  const drugs = filter.drugs.map((drug) => drug.generic);
  const sections = filter.section_groups.map((group) => sectionName(group).toLowerCase());
  return [
    drugs.length > 0 ? `Drugs: ${drugs.join(", ")}.` : "No drug found.",
    sections.length > 0 ? `Sections: ${sections.join(", ")}.` : "No section.",
  ].join(" ");
}

function narrowText(trace: RetrievalTrace, result: LabelPassages): string {
  const filter = trace.filter;
  if (!filter) return "No drug named, so every label was searched.";
  const parts: string[] = [];
  const searched = filter.drugs.filter((drug) => drug.set_ids.length > 0);
  if (searched.length > 0) {
    const labels = searched.reduce((sum, drug) => sum + drug.set_ids.length, 0);
    const names = searched.map((drug) =>
      drug.name.toLowerCase() === drug.generic.toLowerCase()
        ? drug.generic
        : `“${drug.name}” as ${drug.generic}`,
    );
    parts.push(`Searched ${names.join(" and ")}: ${count(labels, "label")}.`);
  }
  if (result.drugs_without_label.length > 0) {
    parts.push(`No US label for ${result.drugs_without_label.join(", ")}.`);
  }
  if (filter.unsupported.length > 0) {
    parts.push(`Not in the store: ${filter.unsupported.map((drug) => drug.query).join(", ")}.`);
  }
  if (filter.ignored_section_groups.length > 0) {
    const ignored = filter.ignored_section_groups.map((group) => sectionName(group).toLowerCase());
    parts.push(`Dropped as not a label section: ${ignored.join(", ")}.`);
  }
  if (trace.widened.length > 0) {
    parts.push(
      "None of those labels has the section, so the drug's other labels were searched too.",
    );
  }
  return parts.join(" ") || "No drug named, so every label was searched.";
}

function scoreStep(score: Draft, trace: RetrievalTrace): Draft {
  const similarities = trace.candidates.map((candidate) => candidate.score);
  const range = `${Math.min(...similarities).toFixed(2)} to ${Math.max(...similarities).toFixed(2)}`;
  const searched = `Searched with “${trace.question}”.`;
  if (trace.mode === "bm25") {
    return {
      ...score,
      title: "Score the passages by keywords",
      who: "code",
      line: "Code ranks the drug's passages by the words they share with the question (BM25).",
      state: "done",
      outcome: `${searched} ${count(trace.candidates.length, "passage")} ranked.`,
    };
  }
  const closest = `${searched} The ${count(trace.candidates.length, "closest passage")} have a similarity of ${range}.`;
  return {
    ...score,
    state: "done",
    outcome:
      trace.mode === "hybrid"
        ? `${closest} A keyword search (BM25) ranked the passages as well.`
        : closest,
  };
}

function boostStep(boost: Draft, trace: RetrievalTrace): Draft {
  const kept = trace.candidates.filter((candidate) => candidate.kept);
  const dropped = trace.candidates.length - kept.length;
  const droppedText =
    dropped > 0
      ? ` ${count(dropped, "passage")} below the minimum similarity of ${trace.min_score.toFixed(2)} ${dropped === 1 ? "was" : "were"} dropped.`
      : "";
  if (trace.mode !== "dense") {
    return {
      ...boost,
      title: `Merge the rankings and keep the top ${kept.length}`,
      line: "Code merges the keyword and embedding rankings by place (rank fusion). No AI is asked.",
      state: "done",
      outcome: `${trace.mode === "hybrid" ? "Hybrid search: the +0.15 only changed the order of the embedding ranking. " : ""}Kept ${count(kept.length, "passage")}.${droppedText}`,
    };
  }
  const passages = boostedRanking(
    kept.map((candidate) => ({
      section: sectionName(candidate.section),
      similarity: candidate.score,
      inSection: candidate.in_section_groups,
    })),
    trace.section_group_boost,
  );
  const bonus = trace.section_group_boost.toFixed(2);
  const boosted = passages.filter((passage) => passage.inSection).length;
  const moved = passages.filter((passage) => passage.before !== passage.after).length;
  const bonusText =
    trace.filter?.section_groups.length === 0 || !trace.filter
      ? "No section was guessed, so no passage got the bonus."
      : boosted === 0
        ? "None of the kept passages is in the guessed section."
        : `${count(boosted, "passage")} got +${bonus}; ${moved === 0 ? "the order stayed the same" : `${count(moved, "passage")} changed place`}.`;
  return {
    ...boost,
    title: `Add the +${bonus} and keep the top ${kept.length}`,
    state: "done",
    outcome: `${bonusText}${droppedText}`,
    ranking: { passages, boost: trace.section_group_boost },
  };
}

function answerSteps(turn: Turn, fixed: boolean): Draft[] {
  const write = fromGuide("write-the-answer", "write");
  const watch = fromGuide("watch-for-a-leak", "watch");
  const check = fromGuide("check-the-sources", "check-sources");
  if (fixed) {
    return [write, watch, check].map((step) => ({ ...step, state: "skipped" }));
  }
  if (turn.replaced) {
    return [
      { ...write, state: "done", outcome: "The chat model wrote an answer, which was withdrawn." },
      {
        ...watch,
        state: "done",
        outcome:
          "The marker showed up, so the answer was replaced with a fixed one before the marker reached you.",
      },
      { ...check, state: "skipped", outcome: "A withdrawn answer isn't checked." },
    ];
  }
  if (turn.state !== "done") return [write, watch, check];
  return [
    { ...write, state: "done", outcome: writeOutcome(turn.answer) },
    { ...watch, state: "done", outcome: "The marker never showed up." },
    checkSourcesStep(check, turn),
  ];
}

function writeOutcome(answer: string): string {
  const refs = citedRefs(answer);
  if (refs.length === 0) return "Wrote the answer without citations.";
  return `Wrote the answer, citing ${refs.map((ref) => `[${ref}]`).join(", ")}.`;
}

function checkSourcesStep(check: Draft, turn: Turn): Draft {
  const verdict = turn.sourceCheck;
  if (verdict === null) {
    return { ...check, state: "skipped", outcome: "No check was recorded for this answer." };
  }
  if (!verdict.checked) {
    return {
      ...check,
      state: "failed",
      outcome: "The check failed, so the answer is shown unchecked.",
    };
  }
  const summary = checkSummary(verdict);
  return {
    ...check,
    state: "done",
    outcome: summary?.detail ?? "The answer states no facts to check.",
  };
}

/**
 * The steps numbered in the order the answer ran them, and the pending ones' states from the
 * turn: the first pending step is where the answer is, or where it ended.
 */
function settle(parts: DraftPart[], turn: Turn): TurnFlowPart[] {
  let number = 0;
  let first = true;
  const settled = (draft: Draft): TurnStep => {
    number += 1;
    const step = { ...draft, number: String(number) };
    if (step.state !== "pending") return step as TurnStep;
    const wasFirst = first;
    first = false;
    switch (turn.state) {
      case "queued":
        return { ...step, state: "waiting" };
      case "answering":
        return { ...step, state: wasFirst ? "running" : "waiting" };
      case "stopped":
        return { ...step, state: wasFirst ? "stopped" : "not_reached" };
      case "failed":
        return wasFirst
          ? { ...step, state: "failed", outcome: turn.error }
          : { ...step, state: "not_reached" };
      case "done":
        return { ...step, state: "not_reached" };
    }
  };
  return parts.map((part) => ({ ...part, steps: part.steps.map(settled) }));
}

function count(n: number, noun: string): string {
  return `${n} ${n === 1 ? noun : `${noun}s`}`;
}

function refRange(refs: number[]): string {
  if (refs.length === 1) return `[${refs[0]}]`;
  return `[${Math.min(...refs)}] to [${Math.max(...refs)}]`;
}
