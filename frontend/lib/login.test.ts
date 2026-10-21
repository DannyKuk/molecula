import { afterEach, describe, expect, it, vi } from "vitest";

const URL = "http://localhost:8000/drugs";

// LOGIN_ON and the token getter are read once when the module loads, so each test loads it anew.
async function loadLogin(publishableKey: string) {
  vi.stubEnv("NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", publishableKey);
  vi.resetModules();
  return import("./login");
}

function stubFetch() {
  const fetchMock = vi.fn().mockResolvedValue(Response.json([]));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("fetchWithLogin", () => {
  it("fetches at once and unchanged while the login is off", async () => {
    const { fetchWithLogin } = await loadLogin("");
    const fetchMock = stubFetch();
    const init = { signal: undefined };

    void fetchWithLogin(URL, init);

    expect(fetchMock).toHaveBeenCalledWith(URL, init);
  });

  it("adds the session token next to the request's own headers", async () => {
    const { fetchWithLogin, setGetToken } = await loadLogin("pk_test_x");
    const fetchMock = stubFetch();
    setGetToken(async () => "token-1");

    await fetchWithLogin(URL, { method: "POST", headers: { Accept: "text/event-stream" } });

    expect(fetchMock).toHaveBeenCalledWith(URL, {
      method: "POST",
      headers: { Accept: "text/event-stream", Authorization: "Bearer token-1" },
    });
  });

  it("waits for Clerk's getToken when a request starts before it is handed over", async () => {
    const { fetchWithLogin, setGetToken } = await loadLogin("pk_test_x");
    const fetchMock = stubFetch();

    const pending = fetchWithLogin(URL, {});
    setGetToken(async () => "token-2");
    await pending;

    expect(fetchMock).toHaveBeenCalledWith(URL, { headers: { Authorization: "Bearer token-2" } });
  });

  it("sends no token when nobody is signed in", async () => {
    const { fetchWithLogin, setGetToken } = await loadLogin("pk_test_x");
    const fetchMock = stubFetch();
    setGetToken(async () => null);

    await fetchWithLogin(URL, {});

    expect(fetchMock).toHaveBeenCalledWith(URL, {});
  });
});
