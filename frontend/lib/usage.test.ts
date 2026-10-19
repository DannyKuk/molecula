import { describe, expect, it } from "vitest";

import { startTurn } from "./chat-turn";
import { conversationUsage, formatUsage, type Usage } from "./usage";

const ANSWER: Usage = {
  input_tokens: 3000,
  output_tokens: 210,
  total_tokens: 3210,
  cost_usd: 0.0021,
};

function answered(usage: Usage) {
  return { ...startTurn("How does imatinib work?"), state: "done" as const, usage };
}

describe("conversationUsage", () => {
  it("adds up the answers' usage", () => {
    expect(conversationUsage([answered(ANSWER), answered(ANSWER)])).toEqual({
      input_tokens: 6000,
      output_tokens: 420,
      total_tokens: 6420,
      cost_usd: 0.0042,
    });
  });

  it("leaves out turns without usage, and has none without any", () => {
    const stopped = { ...startTurn("What does aspirin do?"), state: "stopped" as const };

    expect(conversationUsage([stopped, answered(ANSWER)])).toEqual(ANSWER);
    expect(conversationUsage([stopped])).toBeNull();
  });

  it("is unknown once one answer's is", () => {
    const unknownCost = answered({ ...ANSWER, cost_usd: null });

    const total = conversationUsage([answered(ANSWER), unknownCost]);

    expect(total?.total_tokens).toBe(6420);
    expect(total?.cost_usd).toBeNull();
  });
});

describe("formatUsage", () => {
  it("shows tokens and the cost in dollars", () => {
    expect(formatUsage(ANSWER)).toBe("3,210 tokens · $0.0021");
    expect(formatUsage({ ...ANSWER, cost_usd: 0.000012345 })).toBe("3,210 tokens · $0.000012");
    expect(formatUsage({ ...ANSWER, cost_usd: 1.234 })).toBe("3,210 tokens · $1.2");
  });

  it("shows a local model's answer as free", () => {
    expect(formatUsage({ ...ANSWER, cost_usd: 0 })).toBe("3,210 tokens · $0");
  });

  it("says unknown, not 0, for what a model didn't report", () => {
    expect(
      formatUsage({ input_tokens: null, output_tokens: null, total_tokens: null, cost_usd: null }),
    ).toBe("tokens unknown · cost unknown");
  });
});
