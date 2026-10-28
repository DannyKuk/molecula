import { act, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { LANGUAGE_KEY } from "@/lib/language";

vi.mock("../structure/structure-viewer", () => ({ StructureViewer: vi.fn(() => null) }));

// LOGIN_ON is read once when lib/login loads, so each test loads the page anew.
async function openLanding({ login }: { login: boolean }) {
  vi.stubEnv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", login ? "pk_test_x" : "");
  vi.resetModules();
  const { LandingPage } = await import("./landing-page");
  render(<LandingPage />);
  await act(async () => {});
}

beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal("fetch", vi.fn());
  vi.stubGlobal("matchMedia", () => ({
    matches: false,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
  vi.stubGlobal(
    "IntersectionObserver",
    class {
      observe() {}
      unobserve() {}
      disconnect() {}
    },
  );
});

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("LandingPage", () => {
  it("shows imatinib in 2HYY from the bundled complex, with the wheel left to the page", async () => {
    await openLanding({ login: true });

    const { StructureViewer: viewer } = await import("../structure/structure-viewer");
    const props = vi.mocked(viewer).mock.calls.at(-1)![0];
    expect(props.data.kind === "complex" && props.data.complex.pdb_id).toBe("2HYY");
    expect(props.mode).toBe("site");
    expect(props.scrollsPage).toBe(true);
    expect(screen.getByText("37 atoms · 23 residues · 6 H-bonds")).toBeTruthy();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("sends a visitor to the waitlist or the sign-in while the login is on", async () => {
    await openLanding({ login: true });

    expect(screen.getByRole("link", { name: "Request access" }).getAttribute("href")).toBe(
      "/waitlist",
    );
    expect(screen.getByRole("link", { name: "Sign in" }).getAttribute("href")).toBe("/sign-in");
  });

  it("leads straight to the chat while the login is off", async () => {
    await openLanding({ login: false });

    expect(screen.getByRole("link", { name: "Open the chat" }).getAttribute("href")).toBe("/");
    expect(screen.queryByRole("link", { name: "Sign in" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Request access" })).toBeNull();
  });

  it("follows the recorded question through its four steps", async () => {
    await openLanding({ login: true });

    const steps = screen.getAllByRole("heading", { level: 3 });
    expect(steps.map((step) => step.textContent)).toEqual([
      "Is it safe to answer?",
      "Look it up, don't guess",
      "Cite every fact",
      "Mark what isn't backed",
    ]);
    expect(within(steps[3].closest("li")!).getByText("3 of 3")).toBeTruthy();
  });

  it("speaks German when the reader picked it, and keeps the recorded question in English", async () => {
    localStorage.setItem(LANGUAGE_KEY, "de");
    await openLanding({ login: true });

    expect(screen.getByRole("heading", { level: 1 }).textContent).toBe(
      "Fragen Sie, wie ein Medikament wirkt. Sehen Sie, wie es bindet.",
    );
    expect(
      screen.getByRole("heading", { name: /How does imatinib fight leukemia\?/ }),
    ).toBeTruthy();
    expect(screen.getByRole("link", { name: "Zugang anfragen" })).toBeTruthy();
  });

  it("links dkwebsite.de's legal notice and privacy policy", async () => {
    await openLanding({ login: true });

    expect(screen.getByRole("link", { name: "Legal notice" }).getAttribute("href")).toBe(
      "https://dkwebsite.de/imprint",
    );
    expect(screen.getByRole("link", { name: "Privacy" }).getAttribute("href")).toBe(
      "https://dkwebsite.de/privacy",
    );
  });

  it("links dkwebsite.de's German legal pages in German", async () => {
    localStorage.setItem(LANGUAGE_KEY, "de");
    await openLanding({ login: true });

    expect(screen.getByRole("link", { name: "Impressum" }).getAttribute("href")).toBe(
      "https://dkwebsite.de/de/imprint",
    );
    expect(screen.getByRole("link", { name: "Datenschutz" }).getAttribute("href")).toBe(
      "https://dkwebsite.de/de/privacy",
    );
  });

  it("plays the launch video from the app, muted", async () => {
    await openLanding({ login: true });

    const video = screen.getByLabelText("Molecula's launch video") as HTMLVideoElement;
    expect(video.getAttribute("src")).toBe("/landing/launch.mp4");
    expect(video.muted).toBe(true);
  });
});
