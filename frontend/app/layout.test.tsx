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

describe("the preview card", () => {
  it("is a large card whose links start with SITE_URL", async () => {
    vi.stubEnv("SITE_URL", "https://molecula.example.com");
    vi.resetModules();

    const { metadata } = await import("./layout");

    expect(String(metadata.metadataBase)).toBe("https://molecula.example.com/");
    expect(metadata.openGraph).toMatchObject({ title: "Molecula", type: "website" });
    expect(metadata.twitter).toMatchObject({ card: "summary_large_image" });
  });

  it("serves a 1200 × 630 PNG with its alt text", async () => {
    const card = await import("./opengraph-image");

    const response = await card.default();
    const png = Buffer.from(await response.arrayBuffer());

    expect(response.headers.get("Content-Type")).toBe("image/png");
    // A PNG's width and height are the first two numbers of its IHDR chunk, at bytes 16 and 20.
    expect([png.readUInt32BE(16), png.readUInt32BE(20)]).toEqual([
      card.size.width,
      card.size.height,
    ]);
    expect(card.size).toEqual({ width: 1200, height: 630 });
    expect(card.alt).toContain("Imatinib");
  });
});
