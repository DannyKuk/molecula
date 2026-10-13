import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { HelpDialog, HelpGuide } from "./help-guide";

function openDialog() {
  const onAsk = vi.fn();
  render(<HelpDialog onAsk={onAsk} />);
  const help = screen.getByRole("button", { name: "Help" });
  fireEvent.click(help);
  return { onAsk, help, dialog: screen.getByRole("dialog", { name: "How to use Molecula" }) };
}

async function expectClosed() {
  await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
}

function pressOutside(element: Element) {
  fireEvent.pointerDown(element);
  fireEvent.mouseDown(element);
  fireEvent.pointerUp(element);
  fireEvent.mouseUp(element);
  fireEvent.click(element);
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
  it("opens from the ? button and closes with its Close button, which has the focus", async () => {
    const { help, dialog } = openDialog();
    const close = within(dialog).getByRole("button", { name: "Close" });

    await waitFor(() => expect(document.activeElement).toBe(close));
    fireEvent.click(close);

    await expectClosed();
    await waitFor(() => expect(document.activeElement).toBe(help));
  });

  it("closes on Escape", async () => {
    const { dialog } = openDialog();

    fireEvent.keyDown(dialog, { key: "Escape" });

    await expectClosed();
  });

  it("closes on a click beside it but not on a click inside it", async () => {
    const { dialog } = openDialog();

    pressOutside(within(dialog).getByRole("heading", { name: "What you can ask" }));
    expect(screen.getByRole("dialog")).toBeDefined();

    pressOutside(document.querySelector('[data-slot="dialog-overlay"]')!);
    await expectClosed();
  });

  it("closes and asks the example question that is clicked", async () => {
    const { onAsk, dialog } = openDialog();

    fireEvent.click(within(dialog).getByRole("button", { name: "How does imatinib work?" }));

    await expectClosed();
    expect(onAsk).toHaveBeenCalledExactlyOnceWith("How does imatinib work?");
  });

  it("isn't shown until the ? button is pressed", () => {
    render(<HelpDialog onAsk={vi.fn()} />);

    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
