import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { loadBenchmark } from "@/lib/embedding-benchmark";
import { TINY_RUN } from "@/lib/test-benchmark";

import { QuestionView } from "./question-view";

const BENCHMARK = loadBenchmark(TINY_RUN);

function renderQuestion(index: number) {
  render(
    <QuestionView benchmark={BENCHMARK} question={BENCHMARK.questions[index]} scope="in_drug" />,
  );
}

describe("QuestionView", () => {
  it("shows the question with its answer key, the evidence highlighted", () => {
    renderQuestion(0);
    expect(screen.getByText("What is lisinopril for?")).toBeDefined();
    const marks = screen.getAllByText("lowers blood pressure", { selector: "mark" });
    expect(marks).toHaveLength(2);
    expect(screen.getByText("“treats hypertension”")).toBeDefined();
  });

  it("groups the models by the passage they ranked first, with whether it holds the answer", () => {
    renderQuestion(0);
    const [appCard, otherCard] = screen.getAllByRole("article");

    expect(within(appCard).getByText("Zestril · Warnings")).toBeDefined();
    expect(within(appCard).getByText("Doesn't hold the answer")).toBeDefined();
    expect(
      within(appCard)
        .getAllByRole("listitem")
        .map((li) => li.textContent),
    ).toEqual(["bge-m3 (app)"]);

    expect(within(otherCard).getByText("Zestril · Indications and usage")).toBeDefined();
    expect(within(otherCard).getByText("Holds the answer")).toBeDefined();
    expect(
      within(otherCard)
        .getAllByRole("listitem")
        .map((li) => li.textContent),
    ).toEqual(["bge-small", "Qwen3-Embedding-8B", "gemini-embedding-2"]);
  });

  it("says how many models found the answer and where the app's model ranked it", () => {
    renderQuestion(0);
    expect(screen.getByText("3 of 4 models")).toBeDefined();
    expect(screen.getByText(/bge-m3, the model the app uses: not in the top 10\./)).toBeDefined();
  });

  it("puts every model on one card when they all ranked the same passage first", () => {
    renderQuestion(2);
    expect(screen.getAllByRole("article")).toHaveLength(1);
    expect(
      screen.getByText("1 different passages; models that picked the same one share a card.", {
        exact: false,
      }),
    ).toBeDefined();
  });
});
