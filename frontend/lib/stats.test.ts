import { describe, expect, it } from "vitest";

import { compact, ranked, typicalWaitMs, usageTotals } from "./stats";
import { EMPTY_STATS, STATS } from "./test-stats";

describe("usageTotals", () => {
  it("adds up the requests, answers, tokens and cost over the days", () => {
    expect(usageTotals(STATS.usage.days)).toEqual({
      requests: 5,
      answered: 3,
      inputTokens: 27000,
      outputTokens: 1600,
      costUsd: 0,
    });
  });
});

describe("typicalWaitMs", () => {
  it("is the median of the daily medians, skipping days without an answer", () => {
    expect(typicalWaitMs(STATS.usage.days)).toBe(13000);
    expect(typicalWaitMs([STATS.usage.days[0]])).toBe(12000);
  });

  it("is null without an answered request", () => {
    expect(typicalWaitMs(EMPTY_STATS.usage.days)).toBeNull();
  });
});

describe("ranked", () => {
  it("sorts the counts from most to least and drops zeros", () => {
    expect(ranked({ a: 1, b: 0, c: 4 })).toEqual([
      ["c", 4],
      ["a", 1],
    ]);
  });
});

describe("compact", () => {
  it("keeps numbers below ten thousand whole and shortens the rest", () => {
    expect(compact(1284)).toBe("1,284");
    expect(compact(28600)).toBe("29K");
    expect(compact(5_500_000)).toBe("5.5M");
    expect(compact(2_000_000)).toBe("2M");
  });
});
