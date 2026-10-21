import { act, render, screen, within } from "@testing-library/react";
import { useRouter } from "next/navigation";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { FLOW_STEPS, WHO } from "@/lib/answer-flow";
import { de } from "@/lib/messages/de";
import { en } from "@/lib/messages/en";
import { memoryHistory } from "@/lib/test-fixtures";

import { HowItAnswers } from "./how-it-answers";

vi.mock("next/navigation", () => ({ useRouter: vi.fn() }));

beforeEach(() => {
  vi.stubGlobal("matchMedia", () => ({
    matches: false,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
  localStorage.clear();
  vi.mocked(useRouter).mockReturnValue({ push: vi.fn() } as unknown as ReturnType<
    typeof useRouter
  >);
});

async function openPage() {
  render(<HowItAnswers history={memoryHistory().history} />);
  await act(async () => {});
}

function stepCard(title: string) {
  return within(screen.getByRole("heading", { name: (name) => name.includes(title) }));
}

describe("HowItAnswers", () => {
  it("marks every step with who does it", async () => {
    await openPage();

    for (const step of FLOW_STEPS) {
      expect(stepCard(step.title).getByText(WHO[step.who].label)).toBeTruthy();
    }
  });

  it("gives every step an anchor the Flow tab can link to", async () => {
    await openPage();

    for (const step of FLOW_STEPS) {
      const card = screen.getByRole("heading", { name: (name) => name.includes(step.title) });
      expect(card.closest("li")?.id).toBe(step.id);
    }
  });

  it("explains each tag in the legend", async () => {
    await openPage();

    const legend = within(screen.getByLabelText("Who does a step"));
    expect(legend.getByText(/gpt-oss-20b/)).toBeTruthy();
    expect(legend.getByText(/bge-m3/)).toBeTruthy();
    expect(legend.getByText(/Same input, same result/)).toBeTruthy();
  });

  it("shows how the bonus moved the example's passages", async () => {
    await openPage();

    const rows = within(screen.getByRole("list", { name: "Passages by score" })).getAllByRole(
      "listitem",
    );
    expect(rows.map((row) => row.textContent)).toEqual([
      "Drug interactions+0.15, section asked for0.674th → 1st",
      "Drug and/or lab test interactions+0.15, section asked for0.655th → 2nd",
      "Nursing mothersno bonus0.641st → 3rd",
      "Precautionsno bonus0.642nd → 4th",
      "Nursing mothersno bonus0.633rd → 5th",
    ]);
  });

  it("marks the bonus that was picked in the measurements", async () => {
    await openPage();

    const picked = screen.getByRole("row", { current: true });
    expect(picked.textContent).toBe("+0.1591%97%");
  });
});

describe("HowItAnswers on the cloud setup", () => {
  it("says the cloud setup gives no bonus, with its numbers and the decision doc", async () => {
    await openPage();

    const note = screen.getByText(/The cloud setup, for a server too small for bge-m3/);
    expect(note.textContent).toContain("98% of the questions with no bonus and for 91% with +0.15");
    expect(within(note).getByRole("link").getAttribute("href")).toBe(
      "https://github.com/DannyKuk/molecula/blob/main/docs/decisions/embeddings.md",
    );
  });
});

describe("ordinal", () => {
  it.each([
    [1, "1st"],
    [2, "2nd"],
    [3, "3rd"],
    [4, "4th"],
    [11, "11th"],
    [12, "12th"],
    [13, "13th"],
    [21, "21st"],
  ])("writes %i as %s", (place, written) => {
    expect(en.flow.bars.ordinal(place)).toBe(written);
  });

  it("writes a German place with a full stop", () => {
    expect(de.flow.bars.ordinal(3)).toBe("3.");
  });
});
