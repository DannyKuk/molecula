import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { useRouter } from "next/navigation";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { startTurn } from "@/lib/chat-turn";
import { memoryHistory } from "@/lib/test-fixtures";

import { Benchmarks } from "./benchmarks";

vi.mock("next/navigation", () => ({ useRouter: vi.fn() }));

const push = vi.fn();

afterEach(() => vi.unstubAllGlobals());

beforeEach(() => {
  vi.stubGlobal("matchMedia", () => ({
    matches: false,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
  push.mockReset();
  localStorage.clear();
  vi.mocked(useRouter).mockReturnValue({ push } as unknown as ReturnType<typeof useRouter>);
});

async function openPage() {
  const memory = memoryHistory();
  memory.stored.set("c0", {
    id: "c0",
    title: "Imatinib",
    turns: [{ ...startTurn("Imatinib"), answer: "About imatinib.", state: "done" }],
    createdAt: Date.now(),
    updatedAt: Date.now(),
  });
  render(<Benchmarks history={memory.history} />);
  await act(async () => {});
}

describe("Benchmarks page", () => {
  it("opens a saved chat in the chat from the sidebar", async () => {
    await openPage();
    fireEvent.click(screen.getByRole("button", { name: "Show chats" }));
    const sidebar = within(screen.getByRole("complementary", { name: "Chat history" }));

    fireEvent.click(sidebar.getByRole("button", { name: "Imatinib" }));

    expect(push).toHaveBeenCalledWith("/?chat=c0");
  });

  it("starts a new chat in the chat from the rail", async () => {
    await openPage();

    fireEvent.click(
      within(screen.getByRole("navigation", { name: "Chats" })).getByRole("button", {
        name: "New chat",
      }),
    );

    expect(push).toHaveBeenCalledWith("/");
  });
});
