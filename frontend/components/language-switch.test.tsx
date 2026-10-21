import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LANGUAGE_KEY } from "@/lib/language";
import { memoryHistory, stubPage } from "@/lib/test-fixtures";

import { Chat } from "./chat";
import { DocumentLanguage } from "./language-switch";

vi.mock("./model-status", () => ({ ModelStatus: () => null }));

function browserIn(language: string) {
  vi.spyOn(navigator, "language", "get").mockReturnValue(language);
}

async function openChat() {
  const page = render(
    <>
      <DocumentLanguage />
      <Chat history={memoryHistory().history} />
    </>,
  );
  await act(async () => {});
  return page;
}

/** The switch in the expanded sidebar, which it expands first. */
function languageSwitch() {
  const expand = screen.queryByRole("button", { name: /^(Show chats|Chats zeigen)$/ });
  if (expand) fireEvent.click(expand);
  return within(screen.getByRole("group", { name: /^(Language|Sprache)$/ }));
}

beforeEach(() => {
  stubPage();
  localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  document.documentElement.lang = "en";
});

describe("Language switch", () => {
  it("shows the chat in German in a German browser", async () => {
    browserIn("de-DE");
    await openChat();

    expect(screen.getByRole("textbox", { name: "Zu einem Medikament fragen" })).toBeDefined();
    expect(screen.getByRole("button", { name: "Senden" })).toBeDefined();
    expect(screen.getByRole("link", { name: "Unterstützte Medikamente" })).toBeDefined();
    expect(languageSwitch().getByRole("button", { name: "Deutsch" }).ariaPressed).toBe("true");
    expect(document.documentElement.lang).toBe("de");
  });

  it("shows English in a browser set to any other language", async () => {
    browserIn("fr-FR");
    await openChat();

    expect(screen.getByRole("textbox", { name: "Ask about a medicine" })).toBeDefined();
    expect(languageSwitch().getByRole("button", { name: "English" }).ariaPressed).toBe("true");
  });

  it("switches to English and keeps the choice after a reload", async () => {
    browserIn("de-DE");
    const page = await openChat();

    fireEvent.click(languageSwitch().getByRole("button", { name: "English" }));

    expect(screen.getByRole("button", { name: "Send" })).toBeDefined();
    expect(document.documentElement.lang).toBe("en");
    expect(localStorage.getItem(LANGUAGE_KEY)).toBe("en");
    page.unmount();
    await openChat();
    expect(screen.getByRole("button", { name: "Send" })).toBeDefined();
  });

  it("switches back to German", async () => {
    browserIn("en-US");
    await openChat();

    fireEvent.click(languageSwitch().getByRole("button", { name: "Deutsch" }));

    expect(screen.getByRole("button", { name: "Senden" })).toBeDefined();
    expect(screen.getByText(/^Molecula ist ein KI-Assistent/)).toBeDefined();
  });

  it("sits in the sidebar, not the chat header, and the rail's button switches it", async () => {
    browserIn("en-US");
    await openChat();
    const header = within(screen.getByRole("banner"));
    expect(header.queryByRole("group", { name: "Language" })).toBeNull();
    expect(header.queryByRole("link", { name: "Benchmarks" })).toBeNull();

    const rail = within(screen.getByRole("navigation", { name: "Chats" }));
    fireEvent.click(rail.getByRole("button", { name: "Language: English" }));

    expect(screen.getByRole("button", { name: "Senden" })).toBeDefined();
    expect(rail.getByRole("button", { name: "Sprache: Deutsch" }).textContent).toBe("de");
  });

  it("keeps the choice until the page closes when the browser refuses storage", async () => {
    browserIn("en-US");
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("denied", "SecurityError");
    });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new DOMException("denied", "SecurityError");
    });
    await openChat();

    fireEvent.click(languageSwitch().getByRole("button", { name: "Deutsch" }));

    expect(screen.getByRole("button", { name: "Senden" })).toBeDefined();
  });
});
