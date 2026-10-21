import { describe, expect, it } from "vitest";

import { browserLanguage } from "./language";

describe("browserLanguage", () => {
  it("is German for every kind of German", () => {
    expect(browserLanguage("de")).toBe("de");
    expect(browserLanguage("de-DE")).toBe("de");
    expect(browserLanguage("de-AT")).toBe("de");
    expect(browserLanguage("DE-ch")).toBe("de");
  });

  it("is English for any other language, or none", () => {
    expect(browserLanguage("en-US")).toBe("en");
    expect(browserLanguage("fr")).toBe("en");
    expect(browserLanguage("")).toBe("en");
    expect(browserLanguage(undefined)).toBe("en");
  });
});
