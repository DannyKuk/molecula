// @vitest-environment node
import { afterEach, describe, expect, it, vi } from "vitest";

// The handler proxy.ts gives clerkMiddleware, called directly with a stand-in for Clerk's auth.
vi.mock("@clerk/nextjs/server", () => ({ clerkMiddleware: (handler: unknown) => handler }));

type Auth = (() => Promise<{ userId: string | null }>) & { protect: () => Promise<void> };
type Handler = (auth: Auth, request: { nextUrl: URL; url: string }) => Promise<Response | void>;

async function visit(pathname: string, { signedIn }: { signedIn: boolean }) {
  vi.stubEnv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "pk_test_x");
  vi.resetModules();
  const handler = (await import("./proxy")).default as unknown as Handler;
  const protect = vi.fn(async () => {});
  const auth = Object.assign(async () => ({ userId: signedIn ? "user_1" : null }), { protect });
  const url = `https://molecula.example${pathname}`;
  const response = await handler(auth, { nextUrl: new URL(url), url });
  return { rewrite: response?.headers.get("x-middleware-rewrite") ?? null, protect };
}

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("the login gate", () => {
  it("shows a visitor who isn't signed in the landing page at /", async () => {
    const { rewrite, protect } = await visit("/", { signedIn: false });

    expect(rewrite).toBe("https://molecula.example/about");
    expect(protect).not.toHaveBeenCalled();
  });

  it("gives a signed-in user the chat at /", async () => {
    const { rewrite, protect } = await visit("/", { signedIn: true });

    expect(rewrite).toBeNull();
    expect(protect).toHaveBeenCalledOnce();
  });

  it("keeps the app's other pages behind the login and lets the landing page through", async () => {
    expect((await visit("/drugs", { signedIn: false })).protect).toHaveBeenCalledOnce();
    expect((await visit("/about", { signedIn: false })).protect).not.toHaveBeenCalled();
  });
});
