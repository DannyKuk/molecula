import { act, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getEmbeddingSetup } from "@/lib/api";
import { TINY_RUN } from "@/lib/test-benchmark";

import { EmbeddingBenchmark } from "./embedding-benchmark";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getEmbeddingSetup: vi.fn(),
}));

const LOCAL = { embedding_model: "BAAI/bge-m3", local: true, section_group_boost: 0.15 };
const CLOUD = {
  embedding_model: "google/gemini-embedding-2",
  local: false,
  section_group_boost: 0,
};

afterEach(() => vi.unstubAllGlobals());

beforeEach(() => {
  vi.stubGlobal("matchMedia", () => ({
    matches: true,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
  vi.mocked(getEmbeddingSetup).mockReset();
});

async function openBenchmark() {
  render(<EmbeddingBenchmark run={TINY_RUN} />);
  await act(async () => {});
}

function intro(): string {
  return screen.getByText(/Every square is one question/).textContent ?? "";
}

function appModelCards(): string[] {
  return screen
    .getAllByRole("button", { name: /open details/ })
    .filter((card) => card.textContent?.includes("the app's model"))
    .map((card) => card.getAttribute("aria-label")!);
}

describe("EmbeddingBenchmark", () => {
  it("marks bge-m3 as the app's model on the local setup", async () => {
    vi.mocked(getEmbeddingSetup).mockResolvedValue(LOCAL);

    await openBenchmark();

    expect(intro()).toContain(
      "The app uses bge-m3, which gets 75% of the questions into its top 5 on an ordinary CPU",
    );
    expect(appModelCards()).toEqual(["bge-m3: open details"]);
  });

  it("marks the cloud model the instance embeds with, and names the local one beside it", async () => {
    vi.mocked(getEmbeddingSetup).mockResolvedValue(CLOUD);

    await openBenchmark();

    expect(intro()).toContain(
      "This instance uses gemini-embedding-2, a cloud model, which gets 75% of the questions " +
        "into its top 5. Run on its own, the app uses bge-m3 instead, which gets 75% on an " +
        "ordinary CPU.",
    );
    expect(appModelCards()).toEqual(["gemini-embedding-2: open details"]);
  });

  it("falls back to the local setup when the backend doesn't answer", async () => {
    vi.mocked(getEmbeddingSetup).mockRejectedValue(new TypeError("Failed to fetch"));

    await openBenchmark();

    expect(intro()).toContain("The app uses bge-m3");
    expect(appModelCards()).toEqual(["bge-m3: open details"]);
  });

  it("marks no model when the instance embeds with one the run didn't measure", async () => {
    vi.mocked(getEmbeddingSetup).mockResolvedValue({
      embedding_model: "mistralai/mistral-embed",
      local: false,
      section_group_boost: 0,
    });

    await openBenchmark();

    expect(intro()).toContain(
      "This instance embeds with mistralai/mistral-embed, which this run didn't measure.",
    );
    expect(appModelCards()).toEqual([]);
  });
});
