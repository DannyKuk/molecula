import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  notFound: () => {
    throw new Error("not found");
  },
}));

// LOGIN_ON is read once when lib/login loads, so the test loads the page anew.
async function loadLoginPage(publishableKey: string) {
  vi.stubEnv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", publishableKey);
  vi.resetModules();
  return (await import("./login-page")).LoginPage;
}

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("LoginPage", () => {
  it("shows the form with the legal notice and the privacy policy under it", async () => {
    const LoginPage = await loadLoginPage("pk_test_x");
    render(<LoginPage>sign-in form</LoginPage>);

    expect(screen.getByText("sign-in form")).toBeTruthy();
    expect(screen.getByRole("link", { name: "Legal notice" }).getAttribute("href")).toBe(
      "https://dkwebsite.de/imprint",
    );
    expect(screen.getByRole("link", { name: "Privacy" }).getAttribute("href")).toBe(
      "https://dkwebsite.de/privacy",
    );
  });
});
