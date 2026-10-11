export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type HealthResponse = {
  status: "ok";
};

export type Drug = {
  cid: number;
  name: string;
  aliases: string[];
  has_3d: boolean;
};

export class ApiError extends Error {
  constructor(
    readonly path: string,
    readonly status: number,
  ) {
    super(`${path} returned HTTP ${status}`);
    this.name = "ApiError";
  }
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, { signal });
  if (!response.ok) {
    throw new ApiError(path, response.status);
  }
  return (await response.json()) as T;
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return getJson<HealthResponse>("/health", signal);
}

/** Every drug in the store, sorted by name. */
export function getDrugs(signal?: AbortSignal): Promise<Drug[]> {
  return getJson<Drug[]>("/drugs", signal);
}
