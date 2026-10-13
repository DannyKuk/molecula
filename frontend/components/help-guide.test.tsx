import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HelpDialog, HelpGuide } from "./help-guide";

function renderDialog() {
  const onAsk = vi.fn();
  const onClose = vi.fn();
  render(<HelpDialog onAsk={onAsk} onClose={onClose} />);
  return { onAsk, onClose, dialog: screen.getByRole("dialog", { name: "How to use Molecula" }) };
}

describe("HelpGuide", () => {
  it("says what Molecula answers, what it won't, where the data comes from and how to cite", () => {
    const { container } = render(<HelpGuide onAsk={vi.fn()} />);
    const text = container.textContent ?? "";

    for (const topic of ["How a drug works", "Targets", "3D structures", "Label facts"]) {
      expect(screen.getByRole("heading", { name: new RegExp(topic) })).toBeDefined();
    }
    expect(text).toContain("How much of a medicine you personally should take");
    expect(text).toContain("Doses meant to harm someone");
    expect(text).toContain("How to make a drug");
    expect(text).toContain("call your local emergency number or poison control");
    for (const source of ["FDA drug labels", "PubChem", "ChEMBL", "Protein Data Bank"]) {
      expect(text).toContain(source);
    }
    expect(text).toContain("A number in brackets, like [1], points to the label passage");
  });

  it("asks an example question when it is clicked", () => {
    const onAsk = vi.fn();
    render(<HelpGuide onAsk={onAsk} />);

    fireEvent.click(
      screen.getByRole("button", { name: "What does the warfarin label warn about?" }),
    );

    expect(onAsk).toHaveBeenCalledExactlyOnceWith("What does the warfarin label warn about?");
  });
});

describe("HelpDialog", () => {
  it("closes with its Close button, which has the focus when it opens", () => {
    const { onClose, dialog } = renderDialog();
    const close = within(dialog).getByRole("button", { name: "Close" });

    expect(document.activeElement).toBe(close);
    fireEvent.click(close);

    expect(onClose).toHaveBeenCalledOnce();
  });

  it("closes on Escape", () => {
    const { onClose } = renderDialog();

    fireEvent.keyDown(document, { key: "Escape" });

    expect(onClose).toHaveBeenCalledOnce();
  });

  it("closes on a click beside it but not on a click inside it", () => {
    const { onClose, dialog } = renderDialog();

    fireEvent.click(dialog);
    expect(onClose).not.toHaveBeenCalled();

    fireEvent.click(dialog.parentElement!);
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("closes and asks the example question that is clicked", () => {
    const { onAsk, onClose, dialog } = renderDialog();

    fireEvent.click(within(dialog).getByRole("button", { name: "How does imatinib work?" }));

    expect(onClose).toHaveBeenCalledOnce();
    expect(onAsk).toHaveBeenCalledExactlyOnceWith("How does imatinib work?");
  });
});
