/** The committed chat-model results file (`lib/benchmarks/chat-models-*.json`, #404), written by
 * `backend/evals/chat_model/benchmark_export.py` from the eval caches and the hand verdicts. */
export type ChatModelRun = {
  meta: { date: string; effort: string; gpu: string; source: string };
  questions: { from_memory: LabelQuestion[]; comparisons: ComparisonQuestion[] };
  models: ChatModel[];
};

export type EvalName = "from_memory" | "comparisons";

export type LabelQuestion = { id: string; question: string; drug: string; section_group: string };

export type ComparisonKind = "comparison" | "3d_comparison" | "control";

export type ComparisonQuestion = {
  id: string;
  question: string;
  drugs: string[];
  kind: ComparisonKind;
};

export type ToolCall = { name: string; args: Record<string, unknown> };

export type Answer = {
  id: string;
  question: string;
  text: string;
  tools: ToolCall[];
  seconds: number;
  from_memory: boolean;
  denies_data: boolean;
  note: string;
  error: boolean;
  passed: boolean;
  passage_returned?: boolean;
  evidence?: boolean;
  kind?: ComparisonKind;
};

type Evidence = { of: number; found: number };

export type ChatModel = {
  id: string;
  name: string;
  local: boolean;
  default: boolean;
  gpu: string | null;
  from_memory: {
    answers: number;
    passed: number;
    from_memory: number;
    denies_data: number;
    passage_returned: number;
    errors: number;
    seconds_p50: number;
    cost_usd: number | null;
  };
  comparisons: {
    answers: number;
    passed: number;
    from_memory: number;
    denies_data: number;
    errors: number;
    evidence: { comparison: Evidence; "3d_comparison": Evidence };
    seconds_p50: number;
    cost_usd: number | null;
  };
  answers: Record<EvalName, Answer[]>;
};

export const EVALS: Record<EvalName, string> = {
  from_memory: "Label questions",
  comparisons: "Comparisons",
};

export type Verdict = "clean" | "memory" | "denies" | "both" | "failed";

export const VERDICTS: Record<Verdict, string> = {
  clean: "No flag",
  memory: "Adds from memory",
  denies: "Denies data it has",
  both: "Both",
  failed: "Failed (time limit)",
};

/** What the reader is told about an answer. A failed answer counts as failed whatever its text
 * says, as in the doc's tables. */
export function verdictOf(answer: Answer): Verdict {
  if (answer.error) return "failed";
  if (answer.from_memory && answer.denies_data) return "both";
  if (answer.from_memory) return "memory";
  if (answer.denies_data) return "denies";
  return "clean";
}

export function isFlagged(answer: Answer): boolean {
  return verdictOf(answer) !== "clean";
}

export function questionsOf(
  run: ChatModelRun,
  name: EvalName,
): (LabelQuestion | ComparisonQuestion)[] {
  return run.questions[name];
}

/** A model's answers to one question, in the order they were asked. */
export function answersTo(model: ChatModel, name: EvalName, question: string): Answer[] {
  return model.answers[name].filter((a) => a.question === question);
}

export function questionText(run: ChatModelRun, name: EvalName, id: string): string {
  return questionsOf(run, name).find((q) => q.id === id)?.question ?? id;
}

/** Both runs' OpenRouter cost, or null on a local model. */
export function runCost(model: ChatModel): number | null {
  const { from_memory, comparisons } = model;
  if (from_memory.cost_usd === null || comparisons.cost_usd === null) return null;
  return from_memory.cost_usd + comparisons.cost_usd;
}

export function formatCost(cost: number): string {
  return `$${cost.toFixed(3)}`;
}

export function formatArgs(args: Record<string, unknown>): string {
  return Object.entries(args)
    .map(([key, value]) => `${key}: ${typeof value === "string" ? value : JSON.stringify(value)}`)
    .join(", ");
}
