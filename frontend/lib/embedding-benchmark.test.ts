import { describe, expect, it } from "vitest";

import run from "@/lib/benchmarks/embeddings-2026-10-12.json";

import {
  type EmbeddingRun,
  answerRanges,
  groupBySection,
  hitsInGroup,
  holdsAnswer,
  loadBenchmark,
  modelGroup,
  previewWindow,
  rankBand,
  recallAt,
  recallCurve,
  showcaseQuestion,
  topPassages,
} from "./embedding-benchmark";
import { TINY_RUN } from "./test-benchmark";

const REAL = loadBenchmark(run as EmbeddingRun);

describe("recall", () => {
  it("counts the questions whose answer ranks within k", () => {
    const ranks = [1, 3, 6, null];
    expect(recallAt(ranks, 1)).toBe(0.25);
    expect(recallAt(ranks, 5)).toBe(0.5);
    expect(recallAt(ranks, 10)).toBe(0.75);
    expect(recallCurve(ranks)).toHaveLength(10);
  });

  it("matches the recall@5 stored for every model in the committed run", () => {
    for (const model of REAL.models) {
      for (const scope of ["in_drug", "whole_index"] as const) {
        expect(recallAt(REAL.ranks[model.label][scope], 5)).toBeCloseTo(
          model.recall_at_5[scope],
          3,
        );
      }
    }
  });
});

describe("rankBand", () => {
  it("sorts a rank into first, the rest of the top 5, 6th to 10th, or not found", () => {
    expect([1, 2, 5, 6, 10, null].map(rankBand)).toEqual([
      "first",
      "top5",
      "top5",
      "top10",
      "top10",
      "missed",
    ]);
  });
});

describe("modelGroup", () => {
  it("puts cloud models in the cloud and local models without a CPU time on the GPU", () => {
    expect(TINY_RUN.models.map(modelGroup)).toEqual(["cpu", "cpu", "gpu", "cloud"]);
  });
});

describe("loadBenchmark", () => {
  const appLabels = (embedding_model: string, local: boolean) =>
    loadBenchmark(run as EmbeddingRun, { embedding_model, local })
      .models.filter((m) => m.isApp)
      .map((m) => m.label);

  it("marks the model the instance embeds with, by the id the backend reports", () => {
    expect(appLabels("BAAI/bge-m3", true)).toEqual(["bge-m3"]);
    expect(appLabels("google/gemini-embedding-2", false)).toEqual(["cloud:gemini-embedding-2"]);
    expect(REAL.app?.label).toBe("bge-m3");
  });

  it("marks one variant of a model run with and without the instruction", () => {
    expect(appLabels("BAAI/bge-small-en-v1.5", true)).toEqual(["bge-small"]);
  });

  it("marks nothing for a model the run didn't measure, or measured only elsewhere", () => {
    const unmeasured = loadBenchmark(run as EmbeddingRun, {
      embedding_model: "mistralai/mistral-embed",
      local: false,
    });
    expect(unmeasured.app).toBeNull();
    expect(showcaseQuestion(unmeasured)).toBe(0);
    expect(appLabels("google/gemini-embedding-2", true)).toEqual([]);
  });
});

describe("groupBySection", () => {
  it("orders the groups as a label reads, puts unknown ones last and counts hits per group", () => {
    const benchmark = loadBenchmark(TINY_RUN);
    expect(benchmark.sections.map((s) => [s.id, s.questions.length])).toEqual([
      ["indications", 1],
      ["warnings", 2],
      ["made_up", 1],
    ]);
    expect(hitsInGroup(benchmark.ranks["bge-m3"].in_drug, benchmark.sections[1])).toBe(1);
  });

  it("keeps all 94 questions of the committed run", () => {
    expect(groupBySection(REAL.questions).flatMap((s) => s.questions)).toHaveLength(94);
  });
});

describe("holdsAnswer and answerRanges", () => {
  const question = TINY_RUN.questions[0];

  it("finds the evidence or a pooled passage in the text", () => {
    expect(holdsAnswer(question, "It lowers blood pressure in adults.")).toBe(true);
    expect(holdsAnswer(question, "It treats hypertension, as studies show.")).toBe(true);
    expect(holdsAnswer(question, "Take with food.")).toBe(false);
  });

  it("finds every occurrence, in order", () => {
    const text = "lowers blood pressure; treats hypertension";
    expect(answerRanges(question, text)).toEqual([
      [0, 21],
      [23, 42],
    ]);
  });
});

describe("topPassages", () => {
  it("groups the models by the passage they ranked first, the app's model first", () => {
    const benchmark = loadBenchmark(TINY_RUN);
    const passages = topPassages(benchmark, benchmark.questions[0]);
    expect(passages.map((p) => [p.id, p.models.map((m) => m.label), p.holdsAnswer])).toEqual([
      ["c2", ["bge-m3"], false],
      ["c1", ["bge-small", "qwen3-8b", "cloud:gemini-embedding-2"], true],
    ]);
  });
});

describe("showcaseQuestion", () => {
  it("picks a question the app's model misses and most others find", () => {
    const benchmark = loadBenchmark(TINY_RUN);
    expect(showcaseQuestion(benchmark)).toBe(0);
  });
});

describe("previewWindow", () => {
  it("keeps a short text whole and cuts a long one around the answer", () => {
    expect(previewWindow("short", [])).toEqual([0, 5]);
    const text = "x".repeat(1000) + "ANSWER" + "y".repeat(1000);
    const [from, to] = previewWindow(text, [[1000, 1006]]);
    expect(from).toBeLessThan(1000);
    expect(to).toBeGreaterThan(1006);
    expect(to - from).toBe(420);
  });
});
