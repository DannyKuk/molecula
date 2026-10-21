import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { useRouter } from "next/navigation";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, getChatModel, getStats } from "@/lib/api";
import { memoryHistory } from "@/lib/test-fixtures";
import { CLOUD_STATS, EMPTY_STATS, STATS } from "@/lib/test-stats";

import { Dashboard } from "./dashboard";

vi.mock("next/navigation", () => ({ useRouter: vi.fn() }));
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getStats: vi.fn(),
  getChatModel: vi.fn(),
}));

afterEach(() => vi.unstubAllGlobals());

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
  vi.mocked(getStats).mockReset().mockResolvedValue(STATS);
  vi.mocked(getChatModel).mockReset().mockResolvedValue({ name: "gpt-oss-20b", local: true });
});

async function openPage() {
  render(<Dashboard history={memoryHistory().history} />);
  await act(async () => {});
}

function usageNumber(label: string) {
  const term = screen.getByText(label, { selector: "dt" });
  return term.parentElement!.textContent;
}

describe("Dashboard page", () => {
  it("shows the knowledge base above the usage numbers of the last 30 days", async () => {
    await openPage();

    expect(getStats).toHaveBeenCalledWith(30, expect.any(AbortSignal));
    const kb = screen.getByRole("region", { name: "Knowledge base" });
    expect(kb.textContent).toContain("133 drugs");
    expect(kb.textContent).toContain("7,012 label passages");
    expect(kb.textContent).toContain("Labels fetched 12 Oct 2026");
    expect(kb.textContent).toContain("Last label update: none has run yet");
    expect(usageNumber("Requests")).toBe("Requests5last 30 days");
    expect(usageNumber("Answered")).toBe("Answered60%3 of 5");
    expect(usageNumber("Typical wait")).toBe("Typical wait13.0 smedian answer time");
    expect(usageNumber("Tokens")).toBe("Tokens29K27K in · 1,600 out");
  });

  it("says a local model costs nothing and draws no cost chart", async () => {
    await openPage();

    expect(usageNumber("Cost")).toBe("Cost$0.00local model, tokens are free");
    expect(screen.queryByRole("heading", { name: "Cost per day" })).toBeNull();
  });

  it("draws the cost per day once a cloud model reported a cost", async () => {
    vi.mocked(getStats).mockResolvedValue(CLOUD_STATS);
    vi.mocked(getChatModel).mockResolvedValue({ name: "openai/gpt-4.1-mini", local: false });

    await openPage();

    expect(usageNumber("Cost")).toBe("Cost$0.03reported by the cloud model");
    expect(screen.getByRole("heading", { name: "Cost per day" })).toBeDefined();
  });

  it("shows an empty state instead of charts when the usage log has no request", async () => {
    vi.mocked(getStats).mockResolvedValue(EMPTY_STATS);

    await openPage();

    expect(screen.getByText("No chat requests in the last 30 days")).toBeDefined();
    expect(screen.queryByRole("img")).toBeNull();
    expect(screen.queryByText("Requests", { selector: "dt" })).toBeNull();
    expect(screen.getByRole("region", { name: "Knowledge base" }).textContent).toContain(
      "133 drugs",
    );
  });

  it("loads the picked range and keeps the old numbers dimmed until it arrives", async () => {
    await openPage();
    let arrive: (stats: typeof STATS) => void = () => {};
    vi.mocked(getStats).mockReturnValue(new Promise((resolve) => (arrive = resolve)));

    fireEvent.click(screen.getByRole("button", { name: "7 days" }));

    expect(getStats).toHaveBeenLastCalledWith(7, expect.any(AbortSignal));
    expect(screen.getByRole("button", { name: "7 days" }).getAttribute("aria-pressed")).toBe(
      "true",
    );
    expect(document.querySelector("[aria-busy=true]")).not.toBeNull();
    await act(async () => arrive(STATS));
    expect(document.querySelector("[aria-busy=true]")).toBeNull();
    expect(usageNumber("Requests")).toBe("Requests5last 7 days");
  });

  it("shows the tool calls, how the guard sorted and the errors", async () => {
    await openPage();

    const tools = within(screen.getByRole("heading", { name: "Tool calls" }).parentElement!);
    expect(tools.getByText("resolve_drug")).toBeDefined();
    const guard = screen.getByRole("heading", {
      name: "How the guard sorted questions",
    }).parentElement!;
    expect(guard.textContent).toContain("3 of 4went to the agent as medicine questions");
    expect(guard.textContent).toContain("Off topic1");
    const errors = screen.getByRole("heading", { name: "Errors" }).parentElement!;
    expect(errors.textContent).toBe("ErrorsTimed out1");
  });

  it("says when there were no errors", async () => {
    vi.mocked(getStats).mockResolvedValue({ ...STATS, usage: { ...STATS.usage, errors: {} } });

    await openPage();

    expect(screen.getByText("No errors in this range.")).toBeDefined();
  });

  it("shows a chart's numbers as a table, one row per day with a request", async () => {
    await openPage();
    const card = screen.getByRole("heading", { name: "Requests per day" }).closest("section")!;

    fireEvent.click(within(card).getByRole("button", { name: "Show table" }));

    const rows = within(card).getAllByRole("row");
    expect(rows.map((row) => row.textContent)).toEqual([
      "DayAnsweredStopped by the userTurned away by a limitError",
      "21 Oct2100",
      "19 Oct1001",
    ]);
  });

  it("shows a readable error when /stats fails", async () => {
    vi.mocked(getStats).mockRejectedValue(new ApiError("/stats", 503));

    await openPage();

    expect(screen.getByRole("alert").textContent).toContain("Could not load the numbers.");
  });

  it("is linked from the sidebar rail", async () => {
    await openPage();

    const rail = within(screen.getByRole("navigation", { name: "Chats" }));
    expect(rail.getByRole("link", { name: "Dashboard" }).getAttribute("href")).toBe("/dashboard");
  });
});
