import { afterEach, describe, expect, it, vi } from "vitest";

import { API_URL, ApiError, getHealth } from "./api";

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
