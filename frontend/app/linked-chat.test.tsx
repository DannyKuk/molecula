import { render, screen } from "@testing-library/react";
import { useRouter, useSearchParams } from "next/navigation";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { stubChatStream } from "@/lib/test-fixtures";

import { LinkedChat } from "./linked-chat";

vi.mock("next/navigation", () => ({ useRouter: vi.fn(), useSearchParams: vi.fn() }));

function openWith(query: string) {
  const replace = vi.fn();
  vi.mocked(useRouter).mockReturnValue({ replace } as unknown as ReturnType<typeof useRouter>);
  vi.mocked(useSearchParams).mockReturnValue(
    new URLSearchParams(query) as unknown as ReturnType<typeof useSearchParams>,
  );
  render(<LinkedChat />);
  return replace;
}

beforeEach(() => {
  vi.spyOn(window, "scrollTo").mockImplementation(() => {});
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("LinkedChat", () => {
  it("asks the question from the link and drops it from the address bar", async () => {
    const stream = stubChatStream();

    const replace = openWith("q=How%20does%20imatinib%20work%3F");

    expect(await screen.findByRole("list", { name: "Conversation" })).toBeDefined();
    expect(stream.sentMessages()).toEqual([{ role: "user", content: "How does imatinib work?" }]);
    expect(replace).toHaveBeenCalledExactlyOnceWith("/", { scroll: false });
  });

  it("opens the empty chat when the link carries no question", () => {
    const stream = stubChatStream();

    const replace = openWith("");

    expect(screen.getByRole("button", { name: "How does imatinib work?" })).toBeDefined();
    expect(stream.fetchMock).not.toHaveBeenCalled();
    expect(replace).not.toHaveBeenCalled();
  });
});
