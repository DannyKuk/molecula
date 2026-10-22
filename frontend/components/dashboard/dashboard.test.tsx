import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { useRouter } from "next/navigation";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, type Stats, getChatModel, getStats, startLabelUpdate } from "@/lib/api";
import { LANGUAGE_KEY } from "@/lib/language";
import { memoryHistory } from "@/lib/test-fixtures";
import { CLOUD_STATS, EMPTY_STATS, STATS } from "@/lib/test-stats";

import { Dashboard } from "./dashboard";

vi.mock("next/navigation", () => ({ useRouter: vi.fn(), usePathname: () => "/dashboard" }));
vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  getStats: vi.fn(),
  getChatModel: vi.fn(),
  startLabelUpdate: vi.fn(),
}));

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

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

function withLabelUpdate(
  labelUpdate: Partial<Stats["label_update"]>,
  labelsFetched = STATS.knowledge_base.labels_fetched_to,
): Stats {
  return {
    ...STATS,
    knowledge_base: { ...STATS.knowledge_base, labels_fetched_to: labelsFetched },
    label_update: { ...STATS.label_update, ...labelUpdate },
  };
}

function knowledgeBase() {
  return screen.getByRole("region", { name: "Knowledge base" });
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
    expect(kb.textContent).toContain("Labels fetched Oct 12, 2026");
    expect(kb.textContent).not.toContain("Last label update");
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
    expect(within(screen.getByRole("main")).queryByRole("img")).toBeNull();
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
      "Oct 212100",
      "Oct 191001",
    ]);
  });

  it("shows a readable error when /stats fails", async () => {
    vi.mocked(getStats).mockRejectedValue(new ApiError("/stats", 503));

    await openPage();

    expect(screen.getByRole("alert").textContent).toContain("Could not load the numbers.");
  });

  it("shows no Update now button unless the backend allows one", async () => {
    await openPage();

    expect(within(knowledgeBase()).queryByRole("button")).toBeNull();
  });

  it("shows when the labels were last updated and what changed", async () => {
    vi.mocked(getStats).mockResolvedValue(
      withLabelUpdate({
        last_run: { finished_at: "2026-10-21T03:04:00Z", outcome: "complete", drugs_changed: 2 },
      }),
    );

    await openPage();

    expect(knowledgeBase().textContent).toContain(
      "Last label update Oct 21, 2026: 2 drugs changed",
    );
  });

  it("says when the last label update failed", async () => {
    vi.mocked(getStats).mockResolvedValue(
      withLabelUpdate({
        last_run: { finished_at: "2026-10-21T03:00:05Z", outcome: "failed", drugs_changed: 0 },
      }),
    );

    await openPage();

    expect(knowledgeBase().textContent).toContain(
      "Last label update Oct 21, 2026: failed (see the backend log)",
    );
  });

  it("starts an update from the button and shows it running until it ends", async () => {
    vi.useFakeTimers();
    vi.mocked(getStats).mockResolvedValue(withLabelUpdate({ can_start: true }));
    vi.mocked(startLabelUpdate).mockResolvedValue({
      last_run: null,
      running: true,
      can_start: true,
    });
    await openPage();

    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Update now" })));

    const button = within(knowledgeBase()).getByRole("button");
    expect(button.textContent).toBe("Updating…");
    expect(button.hasAttribute("disabled")).toBe(true);
    expect(within(knowledgeBase()).getByRole("status").textContent).toBe("Updating the labels…");

    vi.mocked(getStats).mockResolvedValue(
      withLabelUpdate(
        {
          can_start: true,
          last_run: { finished_at: "2026-10-22T09:15:00Z", outcome: "complete", drugs_changed: 1 },
        },
        "2026-10-22T09:14:00Z",
      ),
    );
    await act(async () => vi.advanceTimersByTime(5000));

    expect(knowledgeBase().textContent).toContain("Labels fetched Oct 22, 2026");
    expect(knowledgeBase().textContent).toContain("Last label update Oct 22, 2026: 1 drug changed");
    expect(screen.getByRole("button", { name: "Update now" })).toBeDefined();
  });

  it("says when the update could not be started", async () => {
    vi.mocked(getStats).mockResolvedValue(withLabelUpdate({ can_start: true }));
    vi.mocked(startLabelUpdate).mockRejectedValue(new ApiError("/labels/update", 503));
    await openPage();

    await act(async () => fireEvent.click(screen.getByRole("button", { name: "Update now" })));

    expect(within(knowledgeBase()).getByRole("alert").textContent).toContain(
      "Could not start the update.",
    );
  });

  it("writes its text, numbers and dates in German", async () => {
    localStorage.setItem(LANGUAGE_KEY, "de");
    vi.mocked(getStats).mockResolvedValue(
      withLabelUpdate({
        last_run: { finished_at: "2026-10-21T03:04:00Z", outcome: "complete", drugs_changed: 2 },
      }),
    );

    await openPage();

    expect(screen.getByRole("heading", { name: "Dashboard", level: 1 })).toBeDefined();
    const kb = screen.getByRole("region", { name: "Wissensbasis" });
    expect(kb.textContent).toContain("7.012 Textstellen");
    expect(kb.textContent).toContain("Fachinformationen abgerufen am 12. Okt. 2026");
    expect(kb.textContent).toContain(
      "Letzte Aktualisierung am 21. Okt. 2026: 2 Medikamente geändert",
    );
    expect(usageNumber("Anfragen")).toBe("Anfragen5letzte 30 Tage");
    expect(usageNumber("Beantwortet")).toBe("Beantwortet60\u00a0%3 von 5");
    expect(usageNumber("Typische Wartezeit")).toBe(
      "Typische Wartezeit13,0 smittlere Antwortzeit (Median)",
    );
    expect(usageNumber("Tokens")).toBe("Tokens29 Tsd.27 Tsd. gelesen · 1.600 geschrieben");
    expect(usageNumber("Kosten")).toBe("Kosten0,00\u00a0$lokales Modell, Tokens kosten nichts");
    const guard = screen.getByRole("heading", {
      name: "Wie die Sicherheitsprüfung die Fragen sortiert hat",
    }).parentElement!;
    expect(guard.textContent).toContain("Außerhalb des Themas1");
    const errors = screen.getByRole("heading", { name: "Fehler" }).parentElement!;
    expect(errors.textContent).toBe("FehlerZeit überschritten1");

    const card = screen.getByRole("heading", { name: "Anfragen pro Tag" }).closest("section")!;
    fireEvent.click(within(card).getByRole("button", { name: "Tabelle zeigen" }));
    expect(within(card).getAllByRole("row")[1].textContent).toBe("21. Okt.2100");
    expect(screen.getByRole("button", { name: "7 Tage" })).toBeDefined();
  });

  it("is linked from the sidebar rail", async () => {
    await openPage();

    const rail = within(screen.getByRole("navigation", { name: "Chats" }));
    expect(rail.getByRole("link", { name: "Dashboard" }).getAttribute("href")).toBe("/dashboard");
  });
});
