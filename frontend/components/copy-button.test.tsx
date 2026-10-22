import { act, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LANGUAGE_KEY } from "@/lib/language";

import { CopyButton } from "./copy-button";

function stubClipboard(writeText: (text: string) => Promise<void>) {
  Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
}

afterEach(() => {
  Reflect.deleteProperty(navigator, "clipboard");
  vi.useRealTimers();
  localStorage.clear();
});

async function click(name: string) {
  await act(async () => fireEvent.click(screen.getByRole("button", { name })));
}

describe("CopyButton", () => {
  it("copies the text as it is when clicked and says so", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    stubClipboard(writeText);
    let report = "first draft";
    render(<CopyButton text={() => report} label="Copy details" className="" />);
    report = "the report";

    await click("Copy details");

    expect(writeText).toHaveBeenCalledWith("the report");
    expect(screen.getByRole("button").textContent).toBe("Copied");
  });

  it("says when the clipboard refuses", async () => {
    stubClipboard(vi.fn().mockRejectedValue(new Error("denied")));
    render(<CopyButton text={() => "uv run"} label="Copy" className="" />);

    await click("Copy");

    expect(screen.getByRole("button").textContent).toBe("Copy failed");
  });

  it("goes back to its label after two seconds", async () => {
    vi.useFakeTimers();
    stubClipboard(vi.fn().mockRejectedValue(new Error("denied")));
    render(<CopyButton text={() => "uv run"} label="Copy" className="" />);

    await click("Copy");
    act(() => vi.advanceTimersByTime(1999));
    expect(screen.getByRole("button").textContent).toBe("Copy failed");
    act(() => vi.advanceTimersByTime(1));

    expect(screen.getByRole("button").textContent).toBe("Copy");
  });

  it("gives screen readers the fuller name, then the outcome", async () => {
    stubClipboard(vi.fn().mockResolvedValue(undefined));
    render(
      <CopyButton text={() => "{}"} label="Copy" ariaLabel="Copy config" className="absolute" />,
    );

    expect(screen.getByRole("button").textContent).toBe("Copy");
    await click("Copy config");

    expect(screen.getByRole("button", { name: "Copied" })).toBeTruthy();
  });

  it("says the outcome in German", async () => {
    localStorage.setItem(LANGUAGE_KEY, "de");
    stubClipboard(vi.fn().mockRejectedValue(new Error("denied")));
    render(<CopyButton text={() => "{}"} label="Kopieren" className="" />);

    await click("Kopieren");

    expect(screen.getByRole("button").textContent).toBe("Kopieren fehlgeschlagen");
  });
});
