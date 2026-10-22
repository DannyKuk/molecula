import { describe, expect, it } from "vitest";

import { de } from "./messages/de";
import { compact, longDate, seconds, usd, ranked, typicalWaitMs, usageTotals } from "./stats";
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

  it("writes the numbers the German way in German", () => {
    expect(compact(1284, de)).toBe("1.284");
    expect(compact(28600, de)).toBe("29 Tsd.");
    expect(compact(5_500_000, de)).toBe("5,5 Mio.");
  });
});

describe("seconds, usd and longDate", () => {
  it("follow the language", () => {
    expect(seconds(13000)).toBe("13.0 s");
    expect(seconds(13000, de)).toBe("13,0 s");
    expect(seconds(null)).toBe("–");
    expect(usd(0.0312)).toBe("$0.03");
    expect(usd(0.0312, de)).toBe("0,03\u00a0$");
    expect(longDate("2026-10-12T08:45:29Z")).toBe("Oct 12, 2026");
    expect(longDate("2026-10-12T08:45:29Z", de)).toBe("12. Okt. 2026");
  });
});
