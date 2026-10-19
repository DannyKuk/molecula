export type Scope = "in_drug" | "whole_index";
export type Rank = number | null;
export type ModelGroup = "cpu" | "gpu" | "cloud";
export type RankBand = "first" | "top5" | "top10" | "missed";

export type RunModel = {
  label: string;
  model: string;
  dimensions: number;
  index_mb: number;
  weights_mb: number | null;
  query_ms: number;
  query_device: string;
  cpu_query_ms: number | null;
  recall_at_5: Record<Scope, number>;
};

export type RunQuestion = {
  id: string;
  question: string;
  drug: string;
  section_group: string;
  evidence: string;
  pooled_evidence: string[];
};

export type Passage = { section: string; brand: string; text: string };

/** The committed comparison file (`lib/benchmarks/embeddings-*.json`, #273). `ranks` holds, per
 * model and scope, the rank of the first passage with the answer for each question, null when it
 * isn't in the top 10; `top_chunk` the id of the passage each model ranked first within the drug. */
export type EmbeddingRun = {
  meta: { run: string; date: string; questions: number; chunks: number; top_k: number };
  models: RunModel[];
  questions: RunQuestion[];
  ranks: Record<string, Record<Scope, Rank[]>>;
  top_chunk: Record<string, string[]>;
  chunks: Record<string, Passage>;
};

export type Model = RunModel & { name: string; short: string; group: ModelGroup; isApp: boolean };
export type Question = RunQuestion & { index: number };
export type SectionGroup = { id: string; name: string; questions: Question[] };

export type Benchmark = {
  meta: EmbeddingRun["meta"];
  models: Model[];
  questions: Question[];
  sections: SectionGroup[];
  ranks: EmbeddingRun["ranks"];
  topChunk: EmbeddingRun["top_chunk"];
  chunks: EmbeddingRun["chunks"];
};

export const APP_MODEL = "bge-m3";
export const TOP_K = 5;
export const SCOPES: Record<Scope, string> = {
  in_drug: "Within the drug",
  whole_index: "Whole index",
};
export const GROUP_NAMES: Record<ModelGroup, string> = {
  cpu: "Local, runs on a CPU",
  gpu: "Local, needs a GPU",
  cloud: "Cloud API",
};

const MODEL_NAMES: Record<string, [name: string, short: string]> = {
  "bge-small+instruction": ["bge-small + instruction", "bge-small +i"],
  "medembed-small": ["MedEmbed-small", "MedEmbed-small"],
  "bge-large+instruction": ["bge-large + instruction", "bge-large +i"],
  "modernbert-embed": ["modernbert-embed", "modernbert"],
  "qwen3-0.6b": ["Qwen3-Embedding-0.6B", "Qwen3 0.6B"],
  "qwen3-4b": ["Qwen3-Embedding-4B", "Qwen3 4B"],
  "qwen3-8b": ["Qwen3-Embedding-8B", "Qwen3 8B"],
  "cloud:text-embedding-3-small": ["text-embedding-3-small", "OpenAI 3-small"],
  "cloud:text-embedding-3-large": ["text-embedding-3-large", "OpenAI 3-large"],
  "cloud:gemini-embedding-2": ["gemini-embedding-2", "Gemini 2"],
  "cloud:qwen3-8b": ["Qwen3-Embedding-8B (cloud)", "Qwen3 8B cloud"],
};

const SECTION_NAMES: Record<string, string> = {
  indications: "What it's for",
  dosing: "Dosing",
  contraindications: "Who shouldn't take it",
  warnings: "Warnings",
  adverse_reactions: "Side effects",
  interactions: "Interactions",
  specific_populations: "Pregnancy, children, older people",
  overdosage: "Overdose",
  abuse_dependence: "Abuse and dependence",
  pharmacology: "How it works",
  clinical_studies: "Clinical studies",
  product: "Product and ingredients",
  patient_information: "Patient leaflet",
  otc_consumer: "OTC Drug Facts",
};

export function sectionName(id: string): string {
  return SECTION_NAMES[id] ?? id.replaceAll("_", " ");
}

export function modelGroup(model: RunModel): ModelGroup {
  if (model.query_device === "cloud") return "cloud";
  return model.cpu_query_ms === null ? "gpu" : "cpu";
}

/** Questions grouped by section group, in the order a label reads; groups the order doesn't know
 * come last. */
export function groupBySection(questions: Question[]): SectionGroup[] {
  const order = Object.keys(SECTION_NAMES);
  const ids = [...new Set(questions.map((q) => q.section_group))];
  const position = (id: string) => (order.includes(id) ? order.indexOf(id) : order.length);
  return ids
    .sort((a, b) => position(a) - position(b))
    .map((id) => ({
      id,
      name: sectionName(id),
      questions: questions.filter((q) => q.section_group === id),
    }));
}

export function loadBenchmark(run: EmbeddingRun): Benchmark {
  const questions = run.questions.map((q, index) => ({ ...q, index }));
  return {
    meta: run.meta,
    models: run.models.map((m) => {
      const [name, short] = MODEL_NAMES[m.label] ?? [m.label, m.label];
      return { ...m, name, short, group: modelGroup(m), isApp: m.label === APP_MODEL };
    }),
    questions,
    sections: groupBySection(questions),
    ranks: run.ranks,
    topChunk: run.top_chunk,
    chunks: run.chunks,
  };
}

export function isHit(rank: Rank, k: number = TOP_K): boolean {
  return rank !== null && rank <= k;
}

export function rankBand(rank: Rank): RankBand {
  if (rank === null) return "missed";
  if (rank === 1) return "first";
  return rank <= TOP_K ? "top5" : "top10";
}

/** The share of questions whose answer is in the top k. */
export function recallAt(ranks: Rank[], k: number): number {
  return ranks.filter((rank) => isHit(rank, k)).length / ranks.length;
}

export function recallCurve(ranks: Rank[]): number[] {
  return Array.from({ length: 10 }, (_, i) => recallAt(ranks, i + 1));
}

/** How many questions of a section group a model gets into the top 5. */
export function hitsInGroup(ranks: Rank[], group: SectionGroup): number {
  return group.questions.filter((q) => isHit(ranks[q.index])).length;
}

function answerTexts(question: RunQuestion): string[] {
  return [question.evidence, ...question.pooled_evidence].filter(Boolean);
}

/** A passage holds the answer when it contains the evidence or one of the pooled passages. */
export function holdsAnswer(question: RunQuestion, text: string): boolean {
  return answerTexts(question).some((evidence) => text.includes(evidence));
}

/** Where the answer's passages occur in a text, as merged [start, end) ranges. */
export function answerRanges(question: RunQuestion, text: string): [number, number][] {
  const ranges: [number, number][] = [];
  for (const evidence of answerTexts(question)) {
    for (let i = text.indexOf(evidence); i !== -1; i = text.indexOf(evidence, i + 1)) {
      ranges.push([i, i + evidence.length]);
    }
  }
  ranges.sort((a, b) => a[0] - b[0]);
  const merged: [number, number][] = [];
  for (const [start, end] of ranges) {
    const last = merged.at(-1);
    if (last && start <= last[1]) last[1] = Math.max(last[1], end);
    else merged.push([start, end]);
  }
  return merged;
}

export type TopPassage = { id: string; passage: Passage; models: Model[]; holdsAnswer: boolean };

/** The distinct passages the models ranked first for a question, each with the models that
 * picked it: the app's model first, then the most picked. */
export function topPassages(benchmark: Benchmark, question: Question): TopPassage[] {
  const byId = new Map<string, TopPassage>();
  for (const model of benchmark.models) {
    const id = benchmark.topChunk[model.label][question.index];
    const passage = benchmark.chunks[id];
    const entry = byId.get(id) ?? {
      id,
      passage,
      models: [],
      holdsAnswer: holdsAnswer(question, passage.text),
    };
    entry.models.push(model);
    byId.set(id, entry);
  }
  const hasApp = (p: TopPassage) => Number(p.models.some((m) => m.isApp));
  return [...byId.values()].sort(
    (a, b) => hasApp(b) - hasApp(a) || b.models.length - a.models.length,
  );
}

/** A question worth opening first: the app's model misses it and most others find it. */
export function showcaseQuestion(benchmark: Benchmark): number {
  const missedByApp = benchmark.questions.filter(
    (q) => !isHit(benchmark.ranks[APP_MODEL].in_drug[q.index]),
  );
  const found = (q: Question) =>
    benchmark.models.filter((m) => isHit(benchmark.ranks[m.label].in_drug[q.index])).length;
  const best = missedByApp.reduce<Question | undefined>(
    (best, q) => (best && found(best) >= found(q) ? best : q),
    undefined,
  );
  return best?.index ?? 0;
}

export function ordinal(n: number): string {
  const suffixes = ["th", "st", "nd", "rd"];
  const v = n % 100;
  return n + (suffixes[(v - 20) % 10] ?? suffixes[v] ?? suffixes[0]);
}

export function percent(share: number): string {
  return `${Math.round(share * 100)}%`;
}

export function formatSize(mb: number | null): string {
  if (mb === null) return "—";
  if (mb < 1000) return `${Math.round(mb)} MB`;
  const gb = mb / 1000;
  return `${gb >= 10 ? gb.toFixed(1) : gb.toFixed(2)} GB`;
}

export function rankText(rank: Rank): string {
  return rank === null ? "not in the top 10" : `ranked ${ordinal(rank)}`;
}

/** Where a long passage is cut for the preview: around the first answer, about `length`
 * characters, and never cutting the answer's end off. */
export function previewWindow(
  text: string,
  ranges: [number, number][],
  length: number = 420,
): [number, number] {
  if (text.length <= length + 80) return [0, text.length];
  const first = ranges[0];
  let from = Math.max(0, (first?.[0] ?? 0) - Math.floor(length / 3));
  let to = Math.min(text.length, from + length);
  if (first) to = Math.max(to, Math.min(text.length, first[1] + 60));
  if (to - from < length) from = Math.max(0, to - length);
  return [from, to];
}

/** "MEMANTINE HYDROCHLORIDE", "how_supplied" → "Memantine Hydrochloride · How supplied". */
export function passageSource(passage: Passage): string {
  const brand = passage.brand.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase());
  const section = passage.section.replaceAll("_", " ");
  return `${brand} · ${section.charAt(0).toUpperCase()}${section.slice(1)}`;
}

/** The bottom of the recall charts: the lowest recall@1 of any model, rounded down to 10%. */
export function recallFloor(benchmark: Benchmark): number {
  const lowest = Math.min(
    ...benchmark.models.flatMap((m) =>
      Object.values(benchmark.ranks[m.label]).map((ranks) => recallAt(ranks, 1)),
    ),
  );
  return Math.floor(lowest * 10) / 10;
}
