import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { memoryHistory, stubPage } from "@/lib/test-fixtures";
import { THEME_KEY, THEME_SCRIPT } from "@/lib/theme-script";

import { Chat } from "./chat";
import { DocumentTheme } from "./theme-switch";

vi.mock("./model-status", () => ({ ModelStatus: () => null }));

/** A computer whose system setting is dark or light, which the test can change while the page is open. */
function systemIs(scheme: "dark" | "light") {
  const system = { dark: scheme === "dark", listeners: new Set<() => void>() };
  vi.stubGlobal("matchMedia", (query: string) => ({
    get matches() {
      if (query.includes("prefers-color-scheme: dark")) return system.dark;
      return query.includes("min-width");
    },
    addEventListener: (_: string, listener: () => void) => system.listeners.add(listener),
    removeEventListener: (_: string, listener: () => void) => system.listeners.delete(listener),
  }));
  return {
    turn(next: "dark" | "light") {
      system.dark = next === "dark";
      act(() => system.listeners.forEach((notify) => notify()));
    },
  };
}

async function openChat() {
  const page = render(
    <>
      <DocumentTheme />
      <Chat history={memoryHistory().history} />
    </>,
  );
  await act(async () => {});
  return page;
}

function shown() {
  return document.documentElement.dataset.theme;
}

/** The switch in the expanded sidebar, which it expands first. */
function themeSwitch() {
  const expand = screen.queryByRole("button", { name: "Show chats" });
  if (expand) fireEvent.click(expand);
  return within(screen.getByRole("group", { name: "Theme" }));
}

beforeEach(() => {
  stubPage();
  localStorage.clear();
});

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  delete document.documentElement.dataset.theme;
});

describe("Theme switch", () => {
  it("follows the system setting by default, also when it changes", async () => {
    const system = systemIs("dark");
    await openChat();

    expect(shown()).toBe("dark");
    expect(themeSwitch().getByRole("button", { name: "System" }).ariaPressed).toBe("true");

    system.turn("light");
    expect(shown()).toBe("light");
  });

  it("shows the picked theme over the system's and keeps it after a reload", async () => {
    const system = systemIs("dark");
    const page = await openChat();

    fireEvent.click(themeSwitch().getByRole("button", { name: "Light" }));

    expect(shown()).toBe("light");
    expect(localStorage.getItem(THEME_KEY)).toBe("light");
    system.turn("dark");
    expect(shown()).toBe("light");
    page.unmount();
    await openChat();
    expect(shown()).toBe("light");
    expect(themeSwitch().getByRole("button", { name: "Light" }).ariaPressed).toBe("true");
  });

  it("forgets the picked theme when System is picked again", async () => {
    systemIs("light");
    localStorage.setItem(THEME_KEY, "dark");
    await openChat();
    expect(shown()).toBe("dark");

    fireEvent.click(themeSwitch().getByRole("button", { name: "System" }));

    expect(shown()).toBe("light");
    expect(localStorage.getItem(THEME_KEY)).toBeNull();
  });

  it("moves on to the next theme from the rail's button, which names the current one", async () => {
    systemIs("light");
    await openChat();
    const rail = within(screen.getByRole("navigation", { name: "Chats" }));

    fireEvent.click(rail.getByRole("button", { name: "Theme: System" }));
    expect(shown()).toBe("light");
    fireEvent.click(rail.getByRole("button", { name: "Theme: Light" }));
    expect(shown()).toBe("dark");
    fireEvent.click(rail.getByRole("button", { name: "Theme: Dark" }));
    expect(rail.getByRole("button", { name: "Theme: System" })).toBeDefined();
    expect(shown()).toBe("light");
  });

  it("is in the phone drawer, which has no MCP server row", async () => {
    systemIs("light");
    await openChat();

    fireEvent.click(screen.getByRole("button", { name: "Open chats" }));
    const drawer = within(screen.getByRole("dialog"));

    expect(drawer.queryByRole("button", { name: "MCP server" })).toBeNull();
    fireEvent.click(drawer.getByRole("button", { name: "Dark" }));
    expect(shown()).toBe("dark");
  });
});

describe("THEME_SCRIPT", () => {
  function runScript() {
    new Function(THEME_SCRIPT)();
  }

  it("sets the stored theme before the page is drawn", () => {
    systemIs("light");
    localStorage.setItem(THEME_KEY, "dark");

    runScript();

    expect(shown()).toBe("dark");
  });

  it("uses the system setting when nothing is stored or the browser refuses storage", () => {
    systemIs("dark");
    runScript();
    expect(shown()).toBe("dark");

    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new DOMException("denied", "SecurityError");
    });
    systemIs("light");
    runScript();
    expect(shown()).toBe("light");
  });
});
