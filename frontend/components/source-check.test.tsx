import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import type { CheckedClaim, SourceCheck } from "@/lib/chat";
import { IMATINIB_PASSAGES, IMATINIB_SOURCES } from "@/lib/test-fixtures";

import { AnswerMarkdown } from "./answer-markdown";
import { SourceCheckBadge } from "./source-check-badge";

function claim(
  text: string,
  label: CheckedClaim["label"],
  reason = "",
  held_by: number[] = [],
): CheckedClaim {
  return { text, refs: [], label, decided_by: "model", reason, held_by };
}

function renderChecked(text: string, check: SourceCheck) {
  return render(
    <>
      <AnswerMarkdown
        text={text}
        citations={{ sources: IMATINIB_SOURCES, passages: IMATINIB_PASSAGES }}
        sourceCheck={check}
      />
      <SourceCheckBadge check={check} checking={false} />
    </>,
  );
}

function marks(container: HTMLElement): string[] {
  return [...container.querySelectorAll("mark")].map((mark) => mark.textContent ?? "");
}

const BACKED = "Imatinib blocks BCR-ABL [1].";
const UNBACKED = "It was approved in 2001.";
const NOT_A_CLAIM = "Ask your doctor before taking it.";

describe("source check in the answer", () => {
  it("leaves a fully backed answer unmarked and says it was checked", () => {
    const { container } = renderChecked(`${BACKED} ${NOT_A_CLAIM}`, {
      checked: true,
      claims: [claim(BACKED, "supported"), claim(NOT_A_CLAIM, "not_a_claim")],
    });

    expect(marks(container)).toEqual([]);
    expect(screen.getByRole("status").textContent).toBe(
      "Checked against the sources· Every fact is backed by the source it cites.",
    );
  });

  it("underlines the sentence the sources don't back and opens the reason from it", async () => {
    const { container } = renderChecked(`${BACKED} ${UNBACKED} ${NOT_A_CLAIM}`, {
      checked: true,
      claims: [
        claim(BACKED, "supported"),
        claim(UNBACKED, "unsupported", "No source cited for the approval year."),
        claim(NOT_A_CLAIM, "not_a_claim"),
      ],
    });

    expect(marks(container)).toEqual([UNBACKED]);
    expect(screen.getByRole("status").textContent).toBe(
      "Checked against the sources· 1 of 2 facts backed · 1 sentence isn't in Molecula's sources (underlined).",
    );

    fireEvent.click(screen.getByRole("button", { name: UNBACKED }));
    const popover = within(await screen.findByRole("dialog"));
    expect(popover.getByText("Not in Molecula's sources")).toBeDefined();
    expect(popover.getByText("No source cited for the approval year.")).toBeDefined();
  });

  it("adds a chip for the result that holds a sentence the answer cited elsewhere", async () => {
    const sentence = "Imatinib is cleared mostly in the feces [1].";
    const { container } = renderChecked(sentence, {
      checked: true,
      claims: [claim(sentence, "held_elsewhere", "Passage 2 holds it.", [2])],
    });

    expect(marks(container)).toEqual([]);
    expect(container.textContent).toBe(
      "Imatinib is cleared mostly in the feces Gleevec · Mechanism of action Gleevec · Pharmacokinetics." +
        "Checked against the sources· Every fact is in Molecula's sources.",
    );
    fireEvent.click(
      screen.getByRole("button", { name: "Found by the source check: Gleevec · Pharmacokinetics" }),
    );
    const popover = within(await screen.findByRole("dialog"));
    expect(popover.getByText(/the source check found the sentence here/)).toBeDefined();
    expect(popover.getByText(/25% of the dose/)).toBeDefined();
  });

  it("keeps the source chip of an unbacked sentence outside the underline", () => {
    const sentence = "It is cleared by the kidneys [2].";
    const { container } = renderChecked(sentence, {
      checked: true,
      claims: [claim(sentence, "unsupported", "Passage 2 says the liver.")],
    });

    expect(marks(container)).toEqual(["It is cleared by the kidneys"]);
    expect(container.querySelector("mark button")).toBeNull();
    expect(
      screen.getByRole("button", { name: "Sources: Gleevec · Pharmacokinetics" }),
    ).toBeDefined();
  });

  it("underlines the unbacked item of a list, bold text included, but not its heading", () => {
    const answer = "**Imatinib**\n- **Use** – leukemia [1].\n- **Half-life** – 3 days.";
    const { container } = renderChecked(answer, {
      checked: true,
      claims: [
        claim("**Imatinib**\n- **Use** – leukemia [1].", "supported"),
        claim("**Imatinib**\n- **Half-life** – 3 days.", "unsupported", "Not in the passages."),
      ],
    });

    expect(marks(container)).toEqual(["Half-life", " – 3 days."]);
  });

  it("marks nothing and says so quietly when the check failed", () => {
    const { container } = renderChecked(`${BACKED} ${UNBACKED}`, { checked: false, claims: [] });

    expect(marks(container)).toEqual([]);
    expect(screen.getByRole("status").textContent).toBe("Not checked against the sources");
  });

  it("says the answer is being checked until the verdict arrives", () => {
    render(<SourceCheckBadge check={null} checking />);

    expect(screen.getByRole("status").textContent).toBe("Checking the answer against the sources…");
  });

  it("says nothing under an answer that states no drug facts, or one that wasn't checked", () => {
    const { container } = render(
      <>
        <SourceCheckBadge
          check={{ checked: true, claims: [claim(NOT_A_CLAIM, "not_a_claim")] }}
          checking={false}
        />
        <SourceCheckBadge check={null} checking={false} />
      </>,
    );

    expect(container.textContent).toBe("");
  });
});
