import type { Answer, ChatModel, ChatModelRun } from "./chat-model-benchmark";

function answer(id: string, overrides: Partial<Answer> = {}): Answer {
  return {
    id,
    question: id.split("#")[0],
    text: `The answer to ${id}.`,
    tools: [{ name: "search_labels", args: { drug: "ibuprofen" } }],
    seconds: 4,
    from_memory: false,
    denies_data: false,
    note: `Note on ${id}.`,
    error: false,
    passed: true,
    ...overrides,
  };
}

function model(
  id: string,
  overrides: Partial<ChatModel>,
  answers: ChatModel["answers"],
): ChatModel {
  return {
    id,
    name: id.split("/")[1],
    local: false,
    default: false,
    gpu: null,
    from_memory: {
      answers: 2,
      passed: 1,
      from_memory: 1,
      denies_data: 0,
      passage_returned: 2,
      errors: 0,
      seconds_p50: 4,
      cost_usd: 0.01,
    },
    comparisons: {
      answers: 2,
      passed: 1,
      from_memory: 0,
      denies_data: 1,
      errors: 0,
      evidence: { comparison: { of: 2, found: 1 }, "3d_comparison": { of: 0, found: 0 } },
      seconds_p50: 7,
      cost_usd: 0.02,
    },
    answers,
    ...overrides,
  };
}

/** Two label questions and one comparison asked twice, of a cloud and a local model, in the
 * shape of the committed results file. */
export const TINY_CHAT_RUN: ChatModelRun = {
  meta: { date: "2026-10-22", effort: "medium", gpu: "RX 7900 XTX", source: "docs/x.md" },
  questions: {
    from_memory: [
      {
        id: "ibuprofen-dose",
        question: "How much ibuprofen a day?",
        drug: "ibuprofen",
        section_group: "dosing",
      },
      {
        id: "aspirin-kids",
        question: "Can children take aspirin?",
        drug: "aspirin",
        section_group: "warnings",
      },
    ],
    comparisons: [
      {
        id: "compare-ibuprofen-naproxen",
        question: "Compare ibuprofen and naproxen",
        drugs: ["ibuprofen", "naproxen"],
        kind: "comparison",
      },
    ],
  },
  models: [
    model(
      "cloud/luna",
      { default: true },
      {
        from_memory: [
          answer("ibuprofen-dose#1"),
          answer("aspirin-kids#1", {
            from_memory: true,
            passed: false,
            note: "Adds Reye's syndrome.",
          }),
        ],
        comparisons: [
          answer("compare-ibuprofen-naproxen#1", { kind: "comparison", evidence: true }),
          answer("compare-ibuprofen-naproxen#2", {
            kind: "comparison",
            denies_data: true,
            passed: false,
            note: "Says there is no naproxen label.",
          }),
        ],
      },
    ),
    model(
      "local/glm",
      {
        local: true,
        gpu: "RX 7900 XTX",
        from_memory: {
          answers: 2,
          passed: 2,
          from_memory: 0,
          denies_data: 0,
          passage_returned: 1,
          errors: 0,
          seconds_p50: 22.8,
          cost_usd: null,
        },
        comparisons: {
          answers: 2,
          passed: 1,
          from_memory: 0,
          denies_data: 0,
          errors: 1,
          evidence: { comparison: { of: 2, found: 2 }, "3d_comparison": { of: 0, found: 0 } },
          seconds_p50: 71.1,
          cost_usd: null,
        },
      },
      {
        from_memory: [answer("ibuprofen-dose#1"), answer("aspirin-kids#1")],
        comparisons: [
          answer("compare-ibuprofen-naproxen#1", {
            kind: "comparison",
            error: true,
            passed: false,
            text: "",
            note: "Ran past the time limit.",
          }),
          answer("compare-ibuprofen-naproxen#2", { kind: "comparison" }),
        ],
      },
    ),
  ],
};
