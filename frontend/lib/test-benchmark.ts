import type { EmbeddingRun, RunModel } from "./embedding-benchmark";

function model(label: string, overrides: Partial<RunModel>): RunModel {
  return {
    label,
    model: `org/${label}`,
    dimensions: 1024,
    index_mb: 135,
    weights_mb: 2270,
    query_ms: 11,
    query_device: "gpu",
    cpu_query_ms: 37,
    recall_at_5: { in_drug: 0.75, whole_index: 0.5 },
    ...overrides,
  };
}

/** A four-question, four-model comparison in the shape of the committed results file. */
export const TINY_RUN: EmbeddingRun = {
  meta: { run: "tiny", date: "2026-10-12", questions: 4, chunks: 3, top_k: 10 },
  models: [
    model("bge-small", { cpu_query_ms: 8 }),
    model("bge-m3", {}),
    model("qwen3-8b", { cpu_query_ms: null, query_ms: 39, weights_mb: 15100 }),
    model("cloud:gemini-embedding-2", {
      query_device: "cloud",
      cpu_query_ms: null,
      query_ms: 314,
      weights_mb: null,
    }),
  ],
  questions: [
    {
      id: "lisinopril-use",
      question: "What is lisinopril for?",
      drug: "lisinopril",
      section_group: "indications",
      evidence: "lowers blood pressure",
      pooled_evidence: ["treats hypertension"],
    },
    {
      id: "lisinopril-pregnancy",
      question: "Can lisinopril harm a baby?",
      drug: "lisinopril",
      section_group: "warnings",
      evidence: "Fetal toxicity",
      pooled_evidence: [],
    },
    {
      id: "metformin-acidosis",
      question: "What is lactic acidosis?",
      drug: "metformin",
      section_group: "warnings",
      evidence: "lactic acidosis",
      pooled_evidence: [],
    },
    {
      id: "metformin-other",
      question: "Is metformin in a group nobody planned for?",
      drug: "metformin",
      section_group: "made_up",
      evidence: "lactic acidosis",
      pooled_evidence: [],
    },
  ],
  ranks: {
    "bge-small": { in_drug: [1, 2, 7, null], whole_index: [3, 6, null, null] },
    "bge-m3": { in_drug: [null, 3, 8, 1], whole_index: [null, 9, null, 2] },
    "qwen3-8b": { in_drug: [2, 1, 1, 1], whole_index: [2, 1, 2, 1] },
    "cloud:gemini-embedding-2": { in_drug: [1, 1, 4, 2], whole_index: [1, 1, 4, 2] },
  },
  top_chunk: {
    "bge-small": ["c1", "c2", "c3", "c3"],
    "bge-m3": ["c2", "c2", "c3", "c3"],
    "qwen3-8b": ["c1", "c2", "c3", "c3"],
    "cloud:gemini-embedding-2": ["c1", "c2", "c3", "c3"],
  },
  chunks: {
    c1: {
      section: "indications_and_usage",
      brand: "ZESTRIL",
      text: "Zestril lowers blood pressure in adults.",
    },
    c2: {
      section: "warnings",
      brand: "ZESTRIL",
      text: "Fetal toxicity: stop Zestril when pregnancy is detected.",
    },
    c3: {
      section: "boxed_warning",
      brand: "GLUCOPHAGE",
      text: "Postmarketing cases of lactic acidosis.",
    },
  },
};
