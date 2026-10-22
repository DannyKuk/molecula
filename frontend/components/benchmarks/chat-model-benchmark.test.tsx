import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { type Answer, runCost, verdictOf } from "@/lib/chat-model-benchmark";
import { TINY_CHAT_RUN } from "@/lib/test-chat-model-benchmark";

import { ChatModelBenchmark } from "./chat-model-benchmark";

beforeEach(() => {
  vi.stubGlobal("matchMedia", () => ({
    matches: true,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
});

function details() {
  return within(screen.getByRole("complementary", { name: "Details" }));
}

function row(name: string) {
  return screen.getByRole("button", { name: `${name}: open its flagged answers` }).closest("tr")!;
}

describe("verdictOf", () => {
  const base = TINY_CHAT_RUN.models[0].answers.from_memory[0];
  const with_ = (overrides: Partial<Answer>) => verdictOf({ ...base, ...overrides });

  it("tells both flags apart and names an answer with both", () => {
    expect(with_({})).toBe("clean");
    expect(with_({ from_memory: true })).toBe("memory");
    expect(with_({ denies_data: true })).toBe("denies");
    expect(with_({ from_memory: true, denies_data: true })).toBe("both");
  });

  it("counts a failed answer as failed whatever its flags say", () => {
    expect(with_({ error: true, from_memory: true })).toBe("failed");
  });
});

describe("runCost", () => {
  it("adds both runs in the cloud and has none on a local model", () => {
    expect(runCost(TINY_CHAT_RUN.models[0])).toBeCloseTo(0.03);
    expect(runCost(TINY_CHAT_RUN.models[1])).toBeNull();
  });
});

describe("ChatModelBenchmark", () => {
  it("marks the default models and names the GPU the local seconds were measured on", () => {
    render(<ChatModelBenchmark run={TINY_CHAT_RUN} />);

    expect(within(row("luna")).getByText("cloud default")).toBeTruthy();
    expect(within(row("glm")).queryByText(/default/)).toBeNull();
    expect(within(row("glm")).getByText("LM Studio · RX 7900 XTX")).toBeTruthy();
    expect(within(row("glm")).getByText("local")).toBeTruthy();
    expect(screen.getByText(/local models' were measured on an RX 7900 XTX/)).toBeTruthy();
  });

  it("shows a model's failed comparisons beside its clean ones", () => {
    render(<ChatModelBenchmark run={TINY_CHAT_RUN} />);

    expect(within(row("glm")).getByText(/1 failed/)).toBeTruthy();
    expect(within(row("luna")).queryByText(/failed/)).toBeNull();
  });

  it("opens on the default model's flagged answers with their notes", () => {
    render(<ChatModelBenchmark run={TINY_CHAT_RUN} />);

    expect(details().getByText("Label questions: 1 flagged of 2")).toBeTruthy();
    expect(details().getByText("Adds Reye's syndrome.")).toBeTruthy();
    expect(details().getByText("Says there is no naproxen label.")).toBeTruthy();
  });

  it("opens a flagged answer from a model's list, with its tools and its text", () => {
    render(<ChatModelBenchmark run={TINY_CHAT_RUN} />);

    fireEvent.click(details().getByText("Can children take aspirin?"));

    expect(details().getByText("Adds Reye's syndrome.")).toBeTruthy();
    expect(details().getByText("search_labels")).toBeTruthy();
    expect(details().getByText("The answer to aspirin-kids#1.")).toBeTruthy();
  });

  it("opens any answer from its dot in the grid, and says when none arrived", () => {
    render(<ChatModelBenchmark run={TINY_CHAT_RUN} />);

    fireEvent.click(screen.getByRole("button", { name: "Comparisons" }));
    const dots = screen.getAllByRole("button", {
      name: "Compare ibuprofen and naproxen · glm: Failed (time limit)",
    });
    fireEvent.click(dots[0]);

    expect(details().getByText("Ran past the time limit.")).toBeTruthy();
    expect(details().getByText("No answer arrived.")).toBeTruthy();
  });

  it("opens another model's flagged answers from the table", () => {
    render(<ChatModelBenchmark run={TINY_CHAT_RUN} />);

    fireEvent.click(screen.getByRole("button", { name: "glm: open its flagged answers" }));

    expect(details().getByText("Label questions: 0 flagged of 2")).toBeTruthy();
    expect(details().getByText("Comparisons: 1 flagged of 2")).toBeTruthy();
  });
});
