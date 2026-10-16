import { render, screen, waitFor } from "@testing-library/react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { hydrateRoot } from "react-dom/client";
import { renderToString } from "react-dom/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { Chat } from "@/components/chat";
import { chatFrame, stubChatStream, stubPage } from "@/lib/test-fixtures";

import { LinkedChat } from "./linked-chat";

vi.mock("next/navigation", () => ({ useSearchParams: vi.fn() }));

type ActEnvironment = { IS_REACT_ACT_ENVIRONMENT?: boolean };

function openAt(url: string) {
  window.history.replaceState(null, "", url);
  vi.mocked(useSearchParams).mockReturnValue(
    new URLSearchParams(window.location.search) as unknown as ReturnType<typeof useSearchParams>,
  );
}

/** The home page as `app/page.tsx` builds it. */
function homePage() {
  return (
    <Suspense fallback={<Chat />}>
      <LinkedChat />
    </Suspense>
  );
}

/**
 * Server-renders the home page and hydrates it with React's own scheduling, as the browser does:
 * `act` would flush the low-priority hydration work at once and hide what runs in which order.
 */
function hydrateHomePage() {
  const container = document.createElement("div");
  container.innerHTML = renderToString(homePage());
  document.body.append(container);
  const errors: unknown[] = [];
  (globalThis as ActEnvironment).IS_REACT_ACT_ENVIRONMENT = false;
  const root = hydrateRoot(container, homePage(), {
    onRecoverableError: (error) => errors.push(error),
    onUncaughtError: (error) => errors.push(error),
  });
  const unmount = () => {
    root.unmount();
    container.remove();
  };
  return { errors, unmount };
}

beforeEach(() => {
  stubPage();
});

afterEach(() => {
  (globalThis as ActEnvironment).IS_REACT_ACT_ENVIRONMENT = true;
  window.history.replaceState(null, "", "/");
  vi.unstubAllGlobals();
});

describe("LinkedChat", () => {
  it("asks the question from the link and drops it from the address bar", async () => {
    const stream = stubChatStream();
    openAt("/?q=How%20does%20imatinib%20work%3F");

    render(<LinkedChat />);

    expect(await screen.findByRole("list", { name: "Conversation" })).toBeDefined();
    expect(stream.fetchMock).toHaveBeenCalledOnce();
    expect(stream.sentMessages()).toEqual([{ role: "user", content: "How does imatinib work?" }]);
    expect(window.location.search).toBe("");
  });

  it("streams the answer to the link's question when the page is hydrated", async () => {
    const stream = stubChatStream(
      chatFrame({ type: "status", message: "Looking up Aldactone" }) +
        chatFrame({ type: "token", text: "Spironolactone is a diuretic." }),
    );
    openAt("/?q=What%20is%20Aldactone%20used%20for%3F");

    const page = hydrateHomePage();

    expect(await screen.findByText("Spironolactone is a diuretic.")).toBeDefined();
    await waitFor(() => expect(window.location.search).toBe(""));
    expect(screen.getByText("Looking up Aldactone")).toBeDefined();
    expect(screen.getAllByText("What is Aldactone used for?")).toHaveLength(1);
    expect(stream.fetchMock).toHaveBeenCalledOnce();
    expect(page.errors).toEqual([]);
    page.unmount();
  });

  it("opens the empty chat when the link carries no question", () => {
    const stream = stubChatStream();
    openAt("/");

    render(<LinkedChat />);

    expect(screen.getByRole("button", { name: "How does imatinib work?" })).toBeDefined();
    expect(stream.fetchMock).not.toHaveBeenCalled();
    expect(window.location.search).toBe("");
  });
});
