import {
  boostedRanking,
  type FlowStep,
  guideStep,
  type RankedPassage,
  type Who,
} from "./answer-flow";
import type { InputCategory } from "./api";
import { errorText } from "./chat";
import type { Turn } from "./chat-turn";
import { citedRefs, sectionName } from "./citations";
import { en, type Messages } from "./messages/en";
import { CHECKING_ANSWER, checkSummary } from "./source-check";
import { stepLine } from "./step-line";
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
// `backend/src/molecula/main.py`), so their steps are tagged `eitherModel`.
type Flow = Messages["flow"];

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
 * turn: the first one running, stopped or failed, the others waiting or not reached. The text is
 * in the language of `t`; what the tools and models returned stays as they wrote it.
 */
export function turnFlow(turn: Turn, t: Messages = en): TurnFlowPart[] {
  const f = t.flow;
  const tools = turn.steps.filter((step): step is ToolStep => step.tool !== undefined);
  const searches = tools.filter((step) => step.tool.name === "search_labels");
  const fixed = isFixedAnswer(turn, tools);
  // Only an ended answer shows that no lookup is coming: a live one may still call a tool, and an
  // overdose answer's emergency line streams before the chat model has decided anything.
  const answered =
    turn.state === "done" ||
    ((turn.state === "stopped" || turn.state === "failed") && turn.answer !== "");

  const parts: DraftPart[] = [{ title: null, steps: [checkStep(turn, tools, fixed, f)] }];
  if (tools.length === 0) {
    parts.push({ title: null, steps: noLookupSteps(fixed, answered, f) });
  }
  for (const step of tools) {
    const line = stepLine(step, t);
    if (step.tool.name === "search_labels") {
      const index = searches.indexOf(step);
      const title = searches.length > 1 ? f.searchOf(index + 1, searches.length, line) : line;
      parts.push({ title, steps: searchSteps(step.tool, String(index), f) });
    } else {
      parts.push({ title: line, steps: lookupSteps(step.tool, t) });
    }
  }
  parts.push({ title: null, steps: answerSteps(turn, fixed, t) });
  return settle(parts, turn, t);
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

/** The guide's step `id`, with its title and line in the language of `f`. */
function fromGuide(
  id: keyof Flow["guide"],
  key: string,
  f: Flow,
  changes: Partial<Draft> = {},
): Draft {
  const step: FlowStep = guideStep(id);
  return {
    key,
    guide: step.id,
    title: f.guide[id].title,
    who: step.who,
    line: f.guide[id].short,
    state: "pending",
    ...changes,
  };
}

function checkStep(turn: Turn, tools: ToolStep[], fixed: boolean, f: Flow): Draft {
  const step = fromGuide("check-the-question", "check", f, { whoLabel: f.eitherModel });
  const passed = tools.length > 0 || turn.answer !== "" || turn.state === "done";
  if (!passed) return step;
  return { ...step, state: "done", outcome: checkOutcome(turn.category, fixed, f) };
}

function checkOutcome(category: InputCategory | undefined, fixed: boolean, f: Flow): string {
  if (category === "overdose_emergency") return f.overdose;
  if (category && fixed) return f.sortedFixed(f.categories[category]);
  if (fixed) return f.fixed;
  if (category === "ok") return f.sortedOk;
  return f.passed;
}

/** The lookup steps of an answer that looked nothing up. */
function noLookupSteps(fixed: boolean, answered: boolean, f: Flow): Draft[] {
  const decide = fromGuide("decide-what-to-look-up", "decide", f);
  if (!fixed && !answered) return [decide];
  const lookups = [
    fromGuide("narrow-to-the-drug", "narrow", f, { state: "skipped" }),
    fromGuide("score-by-meaning", "score", f, { state: "skipped" }),
    fromGuide("boost-and-keep-five", "boost", f, { state: "skipped" }),
  ];
  return [
    { ...decide, state: "skipped", outcome: fixed ? undefined : f.answeredWithoutLookup },
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

function lookupSteps(tool: ToolRun, t: Messages): Draft[] {
  const f = t.flow;
  const key = tool.id;
  const decide = fromGuide("decide-what-to-look-up", `${key}:decide`, f, {
    state: "done",
    call: callText(tool),
  });
  const lookup: Draft = {
    key: `${key}:lookup`,
    guide: null,
    title: f.lookupTitle,
    who: "code",
    line: f.lookupLine,
    state: "pending",
  };
  const card = cardOf(tool);
  const outcome = lookupOutcome(tool, card, t);
  const shown =
    card?.kind === "complex" || card?.kind === "no_complex" ? [showIn3d(card, key, t)] : [];
  return [decide, outcome ? { ...lookup, state: "done", outcome } : lookup, ...shown];
}

function lookupOutcome(tool: ToolRun, card: Card | null, t: Messages): string | null {
  const f = t.flow;
  if (card === null) return tool.result === undefined ? null : f.done;
  switch (card.kind) {
    case "pending":
      return null;
    case "invalid":
      return f.rejected(card.errors.join("; "));
    case "not_supported":
      return notInStore(card.drugs, f);
    case "drug":
      return f.isInStore(card.result.query, card.result.name);
    case "properties":
      return propertiesOutcome(card.drugs, f);
    case "targets":
      return targetsOutcome(card.result, f);
    case "complex": {
      const target = complexTarget(card.result);
      return f.complexFound(structureTitle(target, t), structureSubtitle(target, t));
    }
    case "no_complex":
      return f.noComplex(card.result.name);
    case "labels":
      return f.passagesFound(card.result.passages.length);
  }
}

function notInStore(drugs: DrugNotSupported[], f: Flow): string {
  return f.notInStore(drugs.map((drug) => drug.query).join(", "));
}

function propertiesOutcome(drugs: (DrugProperties | DrugNotSupported)[], f: Flow): string {
  const found = drugs.filter((drug): drug is DrugProperties => drug.status === "found");
  const missing = drugs.filter((drug): drug is DrugNotSupported => drug.status !== "found");
  const parts =
    found.length === 1
      ? [
          `${found[0].compound.name}: ${found[0].compound.formula}, ${found[0].compound.molecular_weight} g/mol.`,
        ]
      : found.length > 1
        ? [f.sideBySide(found.map((drug) => drug.compound.name).join(", "))]
        : [];
  if (missing.length > 0) parts.push(notInStore(missing, f));
  return parts.join(" ");
}

function targetsOutcome(result: DrugTargetList, f: Flow): string {
  const names = result.targets.map((target) => target.name);
  if (names.length === 0) return f.noMechanism(result.name);
  return f.targets(names.length, names.slice(0, 3).join(", "), Math.max(0, names.length - 3));
}

function complexTarget(complex: DrugComplex): StructureTarget {
  return { cid: complex.cid, name: complex.name, complex };
}

/** What the 3D panel does with a structure the answer looked up: it loads it from the backend,
 * which reads it from the store (`get_drug_complex` and `get_drug_structure` in `api/drugs.py`),
 * and the browser draws it. */
function showIn3d(
  card: Extract<Card, { kind: "complex" | "no_complex" }>,
  key: string,
  t: Messages,
): Draft {
  const f = t.flow;
  return {
    key: `${key}:3d`,
    guide: null,
    title: f.show3dTitle,
    who: "code",
    line: f.show3dLine,
    state: "done",
    outcome:
      card.kind === "complex"
        ? f.shows3d(structureTitle(complexTarget(card.result), t))
        : f.showsMolecule,
  };
}

function searchSteps(tool: ToolRun, index: string, f: Flow): Draft[] {
  const key = `${tool.id || index}`;
  const decide = fromGuide("decide-what-to-look-up", `${key}:decide`, f, {
    state: "done",
    call: callText(tool),
  });
  const trace = tool.trace ?? null;
  const extracted =
    trace?.filter_source === "model"
      ? [
          fromGuide("decide-what-to-look-up", `${key}:extract`, f, {
            title: f.extractTitle,
            whoLabel: f.eitherModel,
            line: f.extractLine,
            state: "done",
            outcome: trace.filter ? filterText(trace, f) : f.noDrugFoundEveryLabel,
          }),
        ]
      : [];
  return [decide, ...extracted, ...searchedSteps(tool, trace, key, f)];
}

/** The filter, scoring and ranking steps of one label search. */
function searchedSteps(tool: ToolRun, trace: RetrievalTrace | null, key: string, f: Flow): Draft[] {
  const narrow = fromGuide("narrow-to-the-drug", `${key}:narrow`, f);
  const score = fromGuide("score-by-meaning", `${key}:score`, f);
  const boost = fromGuide("boost-and-keep-five", `${key}:boost`, f);
  const card = cardOf(tool);
  if (card === null || card.kind === "pending") return [narrow, score, boost];
  const skipped = [score, boost].map((step): Draft => ({ ...step, state: "skipped" }));
  if (card.kind === "invalid") {
    const outcome = f.searchRejected(card.errors.join("; "));
    return [{ ...narrow, state: "done", outcome }, ...skipped];
  }
  if (card.kind === "not_supported") {
    const outcome = f.noneInStore(card.drugs.map((drug) => drug.query).join(", "));
    return [{ ...narrow, state: "done", outcome }, ...skipped];
  }
  if (card.kind !== "labels") return [narrow, score, boost];
  const result = card.result;
  if (!trace) return untracedSteps(result, narrow, score, boost, f);
  const several = searchedDrugs(trace) > 1;
  const narrowed: Draft = {
    ...narrow,
    ...(several && { title: f.narrowSeveralTitle, line: f.narrowSeveralLine }),
    state: "done",
    outcome: narrowText(trace, result, f),
  };
  if (trace.candidates.length === 0) {
    return [
      narrowed,
      { ...score, state: "skipped", outcome: f.noPassageToScore },
      { ...boost, state: "skipped" },
    ];
  }
  const ranked = boostStep(boost, trace, f);
  const severalLine = trace.section_group_boost === 0 ? f.noBoostSeveralLine : f.boostSeveralLine;
  return [
    narrowed,
    scoreStep(score, trace, f),
    several && trace.mode === "dense" ? { ...ranked, line: severalLine } : ranked,
  ];
}

function searchedDrugs(trace: RetrievalTrace): number {
  return trace.filter?.drugs.filter((drug) => drug.set_ids.length > 0).length ?? 0;
}

function untracedSteps(
  result: LabelPassages,
  narrow: Draft,
  score: Draft,
  boost: Draft,
  f: Flow,
): Draft[] {
  const kept = result.passages.length;
  const refs = result.passages.map((passage) => passage.ref);
  const outcome = kept === 0 ? f.noPassageMatched : f.keptNumbered(kept, refRange(refs, f));
  return [
    { ...narrow, state: "done", outcome: f.unrecorded },
    { ...score, state: "done", outcome: f.unrecorded },
    { ...boost, state: "done", outcome },
  ];
}

function filterText(trace: RetrievalTrace, f: Flow): string {
  const filter = trace.filter;
  if (!filter) return f.noDrugNamed;
  const drugs = filter.drugs.map((drug) => drug.generic);
  const sections = filter.section_groups.map(sectionName);
  return [
    drugs.length > 0 ? f.drugs(drugs) : f.noDrug,
    sections.length > 0 ? f.sections(sections) : f.noSection,
  ].join(" ");
}

function narrowText(trace: RetrievalTrace, result: LabelPassages, f: Flow): string {
  const filter = trace.filter;
  if (!filter) return f.noDrugNamed;
  const parts: string[] = [];
  const searched = filter.drugs.filter((drug) => drug.set_ids.length > 0);
  if (searched.length > 0) {
    const labels = searched.reduce((sum, drug) => sum + drug.set_ids.length, 0);
    const names = searched.map((drug) =>
      drug.name.toLowerCase() === drug.generic.toLowerCase()
        ? drug.generic
        : f.searchedAs(drug.name, drug.generic),
    );
    parts.push(f.searched(names, labels));
  }
  if (result.drugs_without_label.length > 0) {
    parts.push(f.noUsLabel(result.drugs_without_label.join(", ")));
  }
  if (filter.unsupported.length > 0) {
    parts.push(f.notInStore(filter.unsupported.map((drug) => drug.query).join(", ")));
  }
  if (filter.ignored_section_groups.length > 0) {
    parts.push(f.droppedSections(filter.ignored_section_groups.map(sectionName)));
  }
  if (trace.widened.length > 0) parts.push(f.widened);
  return parts.join(" ") || f.noDrugNamed;
}

function scoreStep(score: Draft, trace: RetrievalTrace, f: Flow): Draft {
  const similarities = trace.candidates.map((candidate) => candidate.score);
  const range = f.range(Math.min(...similarities).toFixed(2), Math.max(...similarities).toFixed(2));
  const searched = f.searchedWith(trace.question);
  if (trace.mode === "bm25") {
    return {
      ...score,
      title: f.bm25Title,
      who: "code",
      line: f.bm25Line,
      state: "done",
      outcome: `${searched} ${f.ranked(trace.candidates.length)}`,
    };
  }
  const closest = `${searched} ${f.closest(trace.candidates.length, range)}`;
  return {
    ...score,
    state: "done",
    outcome: trace.mode === "hybrid" ? `${closest} ${f.hybridToo}` : closest,
  };
}

function boostStep(boost: Draft, trace: RetrievalTrace, f: Flow): Draft {
  const kept = trace.candidates.filter((candidate) => candidate.kept);
  const dropped = trace.candidates.length - kept.length;
  const droppedText = dropped > 0 ? ` ${f.droppedBelow(dropped, trace.min_score.toFixed(2))}` : "";
  if (trace.mode !== "dense") {
    return {
      ...boost,
      title: f.mergeTitle(kept.length),
      line: f.mergeLine,
      state: "done",
      outcome: `${trace.mode === "hybrid" && trace.section_group_boost > 0 ? f.hybridOrder : ""}${f.kept(kept.length)}${droppedText}`,
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
  // The cloud setup's embedder gives no bonus (#96), so the ranking is the similarity's own.
  if (trace.section_group_boost === 0) {
    return {
      ...boost,
      title: f.keepTitle(kept.length),
      line: f.noBoostLine,
      state: "done",
      outcome: `${f.kept(kept.length)}${droppedText}`,
      ranking: { passages, boost: 0 },
    };
  }
  const bonus = trace.section_group_boost.toFixed(2);
  const boosted = passages.filter((passage) => passage.inSection).length;
  const moved = passages.filter((passage) => passage.before !== passage.after).length;
  const bonusText =
    trace.filter?.section_groups.length === 0 || !trace.filter
      ? f.noSectionGuessed
      : boosted === 0
        ? f.noneInSection
        : f.boosted(boosted, bonus, moved);
  return {
    ...boost,
    title: f.boostTitle(bonus, kept.length),
    state: "done",
    outcome: `${bonusText}${droppedText}`,
    ranking: { passages, boost: trace.section_group_boost },
  };
}

function answerSteps(turn: Turn, fixed: boolean, t: Messages): Draft[] {
  const f = t.flow;
  const write = fromGuide("write-the-answer", "write", f);
  const watch = fromGuide("watch-for-a-leak", "watch", f);
  const check = fromGuide("check-the-sources", "check-sources", f);
  if (fixed) {
    return [write, watch, check].map((step) => ({ ...step, state: "skipped" }));
  }
  if (turn.replaced) {
    return [
      { ...write, state: "done", outcome: f.withdrawnWrite },
      { ...watch, state: "done", outcome: f.markerShowed },
      { ...check, state: "skipped", outcome: f.withdrawnUnchecked },
    ];
  }
  if (turn.state !== "done") return [write, watch, check];
  return [
    { ...write, state: "done", outcome: writeOutcome(turn.answer, f) },
    { ...watch, state: "done", outcome: f.markerNever },
    checkSourcesStep(check, turn, t),
  ];
}

function writeOutcome(answer: string, f: Flow): string {
  const refs = citedRefs(answer);
  if (refs.length === 0) return f.noCitations;
  return f.citing(refs.map((ref) => `[${ref}]`).join(", "));
}

function checkSourcesStep(check: Draft, turn: Turn, t: Messages): Draft {
  const verdict = turn.sourceCheck;
  if (verdict === null) {
    return { ...check, state: "skipped", outcome: t.flow.noCheckRecorded };
  }
  if (!verdict.checked) {
    return { ...check, state: "failed", outcome: t.flow.checkFailed };
  }
  const summary = checkSummary(verdict, t);
  return { ...check, state: "done", outcome: summary?.detail ?? t.flow.noFacts };
}

/**
 * The steps numbered in the order the answer ran them, and the pending ones' states from the
 * turn: the first pending step is where the answer is, or where it ended.
 */
function settle(parts: DraftPart[], turn: Turn, t: Messages): TurnFlowPart[] {
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
          ? { ...step, state: "failed", outcome: errorText(turn.error, t) }
          : { ...step, state: "not_reached" };
      case "done":
        return { ...step, state: "not_reached" };
    }
  };
  return parts.map((part) => ({ ...part, steps: part.steps.map(settled) }));
}

function refRange(refs: number[], f: Flow): string {
  if (refs.length === 1) return `[${refs[0]}]`;
  return f.refRange(Math.min(...refs), Math.max(...refs));
}
