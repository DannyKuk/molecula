import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("@/components/landing/landing-page", () => ({ LandingPage: () => <main>landing</main> }));
vi.mock("@/components/login-provider", () => ({ LoginProvider: () => null }));

// SITE_URL is read once when lib/site loads, so each test loads the files anew with the live address.
async function load<T>(path: string): Promise<T> {
  vi.stubEnv("SITE_URL", "https://molecula.example.com");
  vi.resetModules();
  return import(path);
}

afterEach(() => {
  vi.unstubAllEnvs();
});

describe("what search engines see", () => {
  it("is told to keep off the login pages and where the sitemap is", async () => {
    const { default: robots } = await load<typeof import("./robots")>("./robots");

    expect(robots()).toEqual({
      rules: { userAgent: "*", allow: "/", disallow: ["/sign-in", "/sign-up"] },
      sitemap: "https://molecula.example.com/sitemap.xml",
    });
  });

  it("finds only the landing page in the sitemap, at /", async () => {
    const { default: sitemap } = await load<typeof import("./sitemap")>("./sitemap");

    expect(sitemap()).toEqual([{ url: "https://molecula.example.com/" }]);
  });

  it("counts /about as the landing page at /, described for search", async () => {
    const about = await load<typeof import("./about/page")>("./about/page");

    expect(about.metadata.alternates).toEqual({ canonical: "/" });
    expect(about.metadata.description).toMatch(/FDA drug labels/);

    const html = renderToStaticMarkup(<about.default />);
    const json = html.match(/<script type="application\/ld\+json">(.*?)<\/script>/)?.[1];
    expect(JSON.parse(json ?? "null")).toMatchObject({
      "@type": "WebApplication",
      name: "Molecula",
      url: "https://molecula.example.com/",
    });
    expect(html).toContain("landing");
  });

  it("keeps the app and its login pages out of the index", async () => {
    const { metadata } = await load<typeof import("./(app)/layout")>("./(app)/layout");

    expect(metadata.robots).toEqual({ index: false, follow: false });
  });
});
