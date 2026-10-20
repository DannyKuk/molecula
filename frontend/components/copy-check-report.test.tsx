import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ChatEvent } from "@/lib/chat";
import { applyEvent, startTurn } from "@/lib/chat-turn";

import { ConversationTurn } from "./conversation-turn";
import { CopyCheckReport } from "./copy-check-report";

const CHECKED: ChatEvent[] = [
  { type: "token", text: "It was first sold in 1969." },
  {
    type: "source_check",
    checked: true,
    claims: [
      {
        text: "It was first sold in 1969.",
        refs: [],
        label: "unsupported",
        decided_by: "model",
        reason: "No source gives a year.",
        held_by: [],
      },
    ],
  },
];

const checkedTurn = CHECKED.reduce(applyEvent, startTurn("When was ibuprofen first sold?"));

function stubClipboard(writeText: (text: string) => Promise<void>) {
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
}

afterEach(() => {
  Reflect.deleteProperty(navigator, "clipboard");
});

describe("CopyCheckReport", () => {
  it("copies the report and says so", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    stubClipboard(writeText);
    render(<CopyCheckReport turn={checkedTurn} />);

    fireEvent.click(screen.getByRole("button", { name: "Copy details" }));

    expect(await screen.findByRole("button", { name: "Copied" })).toBeTruthy();
    const report = writeText.mock.calls[0][0] as string;
    expect(report).toContain("When was ibuprofen first sold?");
    expect(report).toContain("Reason: No source gives a year.");
  });

  it("says when the clipboard refuses", async () => {
    stubClipboard(vi.fn().mockRejectedValue(new Error("denied")));
    render(<CopyCheckReport turn={checkedTurn} />);

    fireEvent.click(screen.getByRole("button", { name: "Copy details" }));

    expect(await screen.findByRole("button", { name: "Copy failed" })).toBeTruthy();
  });

  it("shows next to the badge once the check is in, not before", () => {
    const answering = applyEvent(startTurn("When was ibuprofen first sold?"), CHECKED[0]);
    const props = { number: 1, active: true, onAsk: () => {}, chatAnswering: false };
    const { rerender } = render(<ConversationTurn turn={answering} {...props} />);

    expect(screen.queryByRole("button", { name: "Copy details" })).toBeNull();

    rerender(<ConversationTurn turn={checkedTurn} {...props} />);
    expect(screen.getByRole("button", { name: "Copy details" })).toBeTruthy();
  });
});
