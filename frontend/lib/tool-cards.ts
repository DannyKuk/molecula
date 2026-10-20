import type { Resolution, Suggestion } from "./api";

/** A tool the model called, and what it returned once it has (`ToolCallEvent` and
 * `ToolResultEvent` in `backend/src/molecula/schemas/chat.py`). A label search also has its
 * `trace`; searches saved before the trace was kept have none. */
export type ToolRun = {
  id: string;
  name: string;
  args: Record<string, unknown>;
  result?: unknown;
  trace?: RetrievalTrace;
};

/** A label chunk a search scored, kept or dropped below `min_score` (`Candidate` in
 * `backend/src/molecula/schemas/chat.py`). The ranks are null outside the ranking they belong to. */
export type Candidate = {
  id: string;
  text: string;
  score: number;
  substance: string;
  brand: string | null;
  section: string;
  url: string;
  in_section_groups: boolean;
  dense_rank: number | null;
  bm25_rank: number | null;
  kept: boolean;
};

export type DrugFilter = { name: string; generic: string; set_ids: string[]; narrowed: boolean };

/** What a label search was narrowed to (`LabelFilter` in `schemas/retrieval.py`). */
export type LabelFilter = {
  drugs: DrugFilter[];
  unsupported: Resolution[];
  section_groups: string[];
  ignored_section_groups: string[];
  product_type: "rx" | "otc" | null;
  extraction_error: string | null;
};

/** How one label search ran (`RetrievalTraceEvent` in `schemas/chat.py`): the question it
 * searched with, who chose its filter, the filter (null: the whole index), the ranking and every
 * candidate it scored, kept ones first and best first. */
export type RetrievalTrace = {
  tool_call_id: string;
  question: string;
  translation: { step: string; output: string }[];
  filter: LabelFilter | null;
  filter_source: "model" | "agent";
  widened: "labels"[];
  candidates: Candidate[];
  mode: "dense" | "bm25" | "hybrid";
  min_score: number;
  section_group_boost: number;
};

/** A step of the answer: the progress line, and the tool call it announced, if any. */
export type Step = { text: string; tool?: ToolRun };

// The result shapes of `backend/src/molecula/schemas/tools.py`, as far as the cards show them.

export type DrugNotSupported = {
  status: "not_supported";
  query: string;
  suggestions: Suggestion[];
};

export type ResolvedDrug = {
  status: "found";
  query: string;
  cid: number;
  name: string;
  matched_alias: string;
  match_kind: "name" | "alias" | "pubchem" | "brand";
  source_url: string;
};

export type Compound = {
  cid: number;
  name: string;
  formula: string;
  molecular_weight: number;
  xlogp: number | null;
  tpsa: number | null;
  hbond_donors: number;
  hbond_acceptors: number;
  rotatable_bonds: number;
  heavy_atoms: number;
  source_url: string;
};

export type DrugProperties = { status: "found"; query: string; compound: Compound };

export type Target = {
  target_chembl_id: string;
  name: string;
  target_type: string;
  organism: string | null;
  mechanism: string;
  gene_symbols: string[];
  source_url: string;
};

export type DrugTargetList = { status: "found"; name: string; targets: Target[] };

export type HydrogenBond = {
  residue: string;
  chain: string;
  residue_atom: string;
  ligand_atom: string;
  distance: number;
};

export type ResidueContact = { residue: string; chain: string; distance: number };

export type DrugComplex = {
  status: "found";
  cid: number;
  name: string;
  pdb_id: string;
  target: string | null;
  organism: string | null;
  ligand_code: string;
  caption: string | null;
  hydrogen_bonds: HydrogenBond[];
  contacts: ResidueContact[];
  source_url: string;
};

export type NoComplex = { status: "no_complex"; cid: number; name: string };

export type LabelPassage = {
  id: string;
  ref: number;
  text: string;
  substance: string;
  brand: string | null;
  section: string;
  effective_time: string | null;
  url: string;
};

export type LabelPassages = {
  status: "found";
  question: string;
  drugs_without_label: string[];
  unsupported: DrugNotSupported[];
  passages: LabelPassage[];
};

/** What one step's card shows. `properties` holds one drug, several merged, or a comparison. */
export type Card =
  | { kind: "pending" }
  | { kind: "invalid"; errors: string[] }
  | { kind: "not_supported"; drugs: DrugNotSupported[] }
  | { kind: "drug"; result: ResolvedDrug }
  | { kind: "properties"; drugs: (DrugProperties | DrugNotSupported)[] }
  | { kind: "targets"; result: DrugTargetList }
  | { kind: "complex"; result: DrugComplex }
  | { kind: "no_complex"; result: NoComplex }
  | {
      kind: "labels";
      result: LabelPassages;
      drug: string | null;
      section: string | null;
      trace: RetrievalTrace | null;
    };

/** A step as the list shows it; a step without a card is a plain line. */
export type CardStep = { text: string; card: Card | null };

/** The card for a step's tool, or null for a step that ran none or a tool without a card. */
export function cardOf(tool: ToolRun | undefined): Card | null {
  if (!tool) return null;
  if (tool.result === undefined) return { kind: "pending" };
  const result = tool.result as { status?: string } | null;
  if (typeof result !== "object" || result === null) return null;
  if (result.status === "invalid_arguments") {
    return { kind: "invalid", errors: (result as { errors: string[] }).errors };
  }
  switch (tool.name) {
    case "resolve_drug":
      return found(result, (drug: ResolvedDrug) => ({ kind: "drug", result: drug }));
    case "get_properties":
      return found(result, (drug: DrugProperties) => ({ kind: "properties", drugs: [drug] }));
    case "get_targets":
      return found(result, (list: DrugTargetList) => ({ kind: "targets", result: list }));
    case "get_complex":
      if (result.status === "no_complex") {
        return { kind: "no_complex", result: result as NoComplex };
      }
      return found(result, (complex: DrugComplex) => ({ kind: "complex", result: complex }));
    case "compare_drugs":
      return {
        kind: "properties",
        drugs: (result as { drugs: (DrugProperties | DrugNotSupported)[] }).drugs,
      };
    case "search_labels":
      if (result.status === "not_supported") {
        return { kind: "not_supported", drugs: (result as { drugs: DrugNotSupported[] }).drugs };
      }
      return {
        kind: "labels",
        result: result as LabelPassages,
        drug: stringArg(tool.args.drug),
        section: stringArg(tool.args.section),
        trace: tool.trace ?? null,
      };
    default:
      return null;
  }
}

function found<T>(result: { status?: string }, card: (result: T) => Card): Card {
  if (result.status === "not_supported") {
    return { kind: "not_supported", drugs: [result as DrugNotSupported] };
  }
  return card(result as T);
}

function stringArg(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

/**
 * The steps with their cards. With `mergeProperties`, the properties of several drugs, each
 * looked up on its own, show as one table at the first lookup's place.
 */
export function cardSteps(steps: Step[], mergeProperties: boolean): CardStep[] {
  const shown = steps.map((step) => ({ text: step.text, card: cardOf(step.tool) }));
  if (!mergeProperties) return shown;
  const lookups = shown.filter(
    (step) =>
      step.card?.kind === "properties" &&
      step.card.drugs.length === 1 &&
      step.card.drugs[0].status === "found",
  );
  if (lookups.length < 2) return shown;
  const drugs = lookups.flatMap((step) =>
    step.card?.kind === "properties" ? step.card.drugs : [],
  );
  const names = drugs.map((drug) => (drug.status === "found" ? drug.compound.name : drug.query));
  const merged: CardStep = {
    text: `Getting the properties of ${names.join(", ")}`,
    card: { kind: "properties", drugs },
  };
  return shown
    .filter((step) => step === lookups[0] || !lookups.includes(step))
    .map((step) => (step === lookups[0] ? merged : step));
}

/** A drug the answer shows in 3D: in its reviewed complex, or alone when it has none. */
export type StructureTarget = { cid: number; name: string; complex: DrugComplex | null };

/** The drugs whose structure the turn looked up, once each, in the order they were looked up. */
export function structuresOf(steps: Step[]): StructureTarget[] {
  const targets = new Map<number, StructureTarget>();
  for (const step of steps) {
    const card = cardOf(step.tool);
    if (card?.kind === "complex" || card?.kind === "no_complex") {
      const { cid, name } = card.result;
      if (!targets.has(cid)) {
        targets.set(cid, { cid, name, complex: card.kind === "complex" ? card.result : null });
      }
    }
  }
  return [...targets.values()];
}

/** "Imatinib in ABL1", or the drug's name alone when it has no complex. */
export function structureTitle(target: StructureTarget): string {
  const name = target.name.charAt(0).toUpperCase() + target.name.slice(1);
  return target.complex
    ? `${name} in ${target.complex.target ?? `PDB ${target.complex.pdb_id}`}`
    : name;
}

/** "PDB 2HYY · Homo sapiens · 5 hydrogen bonds", or why the drug shows alone. */
export function structureSubtitle(target: StructureTarget): string {
  if (!target.complex) return "the molecule alone: no reviewed structure with its target";
  const { pdb_id, organism, hydrogen_bonds } = target.complex;
  const bonds = hydrogen_bonds.length;
  return [`PDB ${pdb_id}`, organism, `${bonds} hydrogen ${bonds === 1 ? "bond" : "bonds"}`]
    .filter(Boolean)
    .join(" · ");
}
