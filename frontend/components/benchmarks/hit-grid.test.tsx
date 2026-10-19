import { fireEvent, render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { loadBenchmark } from "@/lib/embedding-benchmark";
import { TINY_RUN } from "@/lib/test-benchmark";

import { EmbeddingBenchmark } from "./embedding-benchmark";
import { HitGrid } from "./hit-grid";

const BENCHMARK = loadBenchmark(TINY_RUN);

beforeEach(() => {
  vi.stubGlobal("matchMedia", () => ({
    matches: false,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
});

function renderGrid(onQuestion = vi.fn()) {
  render(
    <HitGrid
      benchmark={BENCHMARK}
      scope="in_drug"
      selected={null}
      onQuestion={onQuestion}
      onModel={vi.fn()}
    />,
  );
  return onQuestion;
}

describe("HitGrid", () => {
  it("groups the questions by section group, in the order a label reads", () => {
    renderGrid();
    const groups = screen.getAllByRole("rowheader").map((th) => th.textContent);
    expect(groups).toEqual(["What it's for (1)", "Warnings (2)", "made up (1)"]);
  });

  it("counts each model's top-5 hits per group", () => {
    renderGrid();
    expect(screen.getByTitle("bge-m3: 1 of 2 in the top 5").textContent).toBe("1");
    expect(screen.getByTitle("Qwen3-Embedding-8B: 2 of 2 in the top 5").textContent).toBe("2");
  });

  it("labels every square with its question, model and rank", () => {
    renderGrid();
    expect(
      screen.getByRole("button", {
        name: "What is lisinopril for? · bge-m3: answer not in the top 10",
      }),
    ).toBeDefined();
    expect(screen.getAllByRole("button", { name: /answer/ })).toHaveLength(16);
  });

  it("reports the question and model of a clicked square", () => {
    const onQuestion = renderGrid();
    fireEvent.click(
      screen.getByRole("button", {
        name: "Can lisinopril harm a baby? · bge-small: answer ranked 2nd",
      }),
    );
    expect(onQuestion).toHaveBeenCalledExactlyOnceWith(1, "bge-small");
  });

  it("moves between squares with the arrow keys, one tab stop for the grid", () => {
    renderGrid();
    const first = screen.getByRole("button", {
      name: "What is lisinopril for? · bge-small: answer ranked 1st",
    });
    expect(first.tabIndex).toBe(0);

    first.focus();
    fireEvent.keyDown(first, { key: "ArrowDown" });

    const below = screen.getByRole("button", {
      name: "Can lisinopril harm a baby? · bge-small: answer ranked 2nd",
    });
    expect(document.activeElement).toBe(below);
    expect(below.tabIndex).toBe(0);
    expect(first.tabIndex).toBe(-1);
  });
});

describe("EmbeddingBenchmark", () => {
  it("shows the whole-index ranks after the switch", () => {
    render(<EmbeddingBenchmark run={TINY_RUN} />);
    const square = () =>
      screen.getAllByRole("button", { name: /^What is lisinopril for\? · bge-small:/ })[0];
    expect(square().getAttribute("aria-label")).toMatch(/answer ranked 1st$/);

    fireEvent.click(screen.getByRole("button", { name: "Whole index" }));

    expect(square().getAttribute("aria-label")).toMatch(/answer ranked 3rd$/);
    expect(screen.getByTitle("bge-m3: 0 of 2 in the top 5")).toBeDefined();
  });

  it("selects the clicked square's question and opens it in a sheet on a phone", () => {
    render(<EmbeddingBenchmark run={TINY_RUN} />);
    const square = screen.getByRole("button", {
      name: "What is lactic acidosis? · Qwen3-Embedding-8B: answer ranked 1st",
    });

    fireEvent.click(square);

    expect(square.getAttribute("aria-pressed")).toBe("true");
    const sheet = screen.getByRole("dialog");
    expect(within(sheet).getByText("What is lactic acidosis?")).toBeDefined();
    expect(within(sheet).getByText("Question 3 of 4")).toBeDefined();
  });
});
