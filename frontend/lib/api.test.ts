import { afterEach, describe, expect, it, vi } from "vitest";

import {
  API_URL,
  ApiError,
  getComplex,
  getDrugs,
  getEmbeddingSetup,
  getStats,
  getHealth,
  getStructure,
  resolveDrug,
} from "./api";
import { SMALL_COMPLEX } from "./test-complexes";
import { STATS } from "./test-stats";

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

describe("getStructure", () => {
  it("returns the drug's conformer as SDF text", async () => {
    const sdf = "1983\n  -OEChem-\nM  END\n$$$$\n";
    const fetchMock = stubFetch(new Response(sdf));

    await expect(getStructure(1983)).resolves.toBe(sdf);
    expect(fetchMock).toHaveBeenCalledWith(`${API_URL}/drugs/1983/structure`, {
      signal: undefined,
    });
  });

  it("throws an ApiError with status 404 for a drug without a 3D structure", async () => {
    stubFetch(Response.json({ detail: "insulin glargine has no 3D structure." }, { status: 404 }));

    await expect(getStructure(118984454)).rejects.toMatchObject({
      path: "/drugs/118984454/structure",
      status: 404,
    });
  });
});

describe("getComplex", () => {
  it("returns the drug's complex", async () => {
    const fetchMock = stubFetch(Response.json(SMALL_COMPLEX));

    await expect(getComplex(5291)).resolves.toEqual(SMALL_COMPLEX);
    expect(fetchMock).toHaveBeenCalledWith(`${API_URL}/drugs/5291/complex`, { signal: undefined });
  });
});

describe("getStats", () => {
  it("asks for the picked number of days", async () => {
    const fetchMock = stubFetch(Response.json(STATS));

    await expect(getStats(7)).resolves.toEqual(STATS);
    expect(fetchMock).toHaveBeenCalledWith(`${API_URL}/stats?days=7`, { signal: undefined });
  });
});

describe("getEmbeddingSetup", () => {
  it("returns the instance's embedding model and section bonus", async () => {
    const setup = {
      embedding_model: "google/gemini-embedding-2",
      local: false,
      section_group_boost: 0,
    };
    const fetchMock = stubFetch(Response.json(setup));

    await expect(getEmbeddingSetup()).resolves.toEqual(setup);
    expect(fetchMock).toHaveBeenCalledWith(`${API_URL}/retrieval`, { signal: undefined });
  });
});
