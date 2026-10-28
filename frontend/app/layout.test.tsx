import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("next/font/google", () => ({
  Inter_Tight: () => ({ variable: "inter-tight" }),
  JetBrains_Mono: () => ({ variable: "jetbrains-mono" }),
}));

const clerkProvider = vi.fn(({ children }: { children: ReactNode }) => children);
vi.mock("@clerk/nextjs", () => ({
  ClerkProvider: (props: { children: ReactNode }) => clerkProvider(props),
  useAuth: () => ({ getToken: async () => null }),
}));

// LOGIN_ON is read once when lib/login loads, so each test loads the layouts anew with the login on.
async function loadLayouts() {
  vi.stubEnv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "pk_test_x");
  vi.resetModules();
  clerkProvider.mockClear();
  return {
    RootLayout: (await import("./layout")).default,
    AppLayout: (await import("./(app)/layout")).default,
  };
}

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("the layouts", () => {
  it("keep Clerk out of the landing page, which only the root layout wraps", async () => {
    const { RootLayout } = await loadLayouts();

    const html = renderToStaticMarkup(
      <RootLayout params={Promise.resolve({})}>landing page</RootLayout>,
    );

    expect(html).toContain("landing page");
    expect(clerkProvider).not.toHaveBeenCalled();
  });

  it("wrap the app and its login pages in Clerk", async () => {
    const { AppLayout } = await loadLayouts();

    const html = renderToStaticMarkup(<AppLayout params={Promise.resolve({})}>chat</AppLayout>);

    expect(html).toContain("chat");
    expect(clerkProvider).toHaveBeenCalledOnce();
  });
});
