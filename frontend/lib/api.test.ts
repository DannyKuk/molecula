import { afterEach, describe, expect, it, vi } from "vitest";

import { API_URL, ApiError, getDrugs, getHealth, resolveDrug } from "./api";

function stubFetch(response: Response) {
  const fetchMock = vi.fn().mockResolvedValue(response);
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("getHealth", () => {
  it("returns the backend's status", async () => {
    const fetchMock = stubFetch(Response.json({ status: "ok" }));

    await expect(getHealth()).resolves.toEqual({ status: "ok" });
    expect(fetchMock).toHaveBeenCalledWith(`${API_URL}/health`, { signal: undefined });
  });

  it("throws an ApiError with the status code when the backend answers with an error", async () => {
    stubFetch(new Response("Service Unavailable", { status: 503 }));

    const error = await getHealth().catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ path: "/health", status: 503 });
  });

  it("lets a network failure through", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(getHealth()).rejects.toThrow("Failed to fetch");
  });
});

describe("getDrugs", () => {
  it("returns the supported drugs", async () => {
    const drugs = [{ cid: 5291, name: "imatinib", aliases: ["Gleevec", "Glivec"], has_3d: true }];
    const fetchMock = stubFetch(Response.json(drugs));

    await expect(getDrugs()).resolves.toEqual(drugs);
    expect(fetchMock).toHaveBeenCalledWith(`${API_URL}/drugs`, { signal: undefined });
  });

  it("throws an ApiError when the backend answers with an error", async () => {
    stubFetch(new Response("Internal Server Error", { status: 500 }));

    await expect(getDrugs()).rejects.toMatchObject({ path: "/drugs", status: 500 });
  });
});

describe("resolveDrug", () => {
  it("returns the resolution with the suggestions for an unsupported name", async () => {
    const resolution = {
      query: "Gleevek",
      status: "not_supported",
      compound: null,
      matched_alias: null,
      match_kind: null,
      suggestions: [{ alias: "Gleevec", cid: 5291, name: "imatinib" }],
    };
    const fetchMock = stubFetch(Response.json(resolution));

    await expect(resolveDrug("Gleevek")).resolves.toEqual(resolution);
    expect(fetchMock).toHaveBeenCalledWith(`${API_URL}/drugs/resolve?name=Gleevek`, {
      signal: undefined,
    });
  });

  it("encodes the name in the query string", async () => {
    const fetchMock = stubFetch(Response.json({}));

    await resolveDrug("imatinib mesylate & co");

    expect(fetchMock).toHaveBeenCalledWith(
      `${API_URL}/drugs/resolve?name=imatinib%20mesylate%20%26%20co`,
      { signal: undefined },
    );
  });

  it("throws an ApiError when the backend rejects the name", async () => {
    stubFetch(new Response("Unprocessable Content", { status: 422 }));

    await expect(resolveDrug("<script>")).rejects.toMatchObject({
      path: "/drugs/resolve?name=%3Cscript%3E",
      status: 422,
    });
  });
});
