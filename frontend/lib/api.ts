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

export type Compound = {
  cid: number;
  name: string;
  inchikey: string;
  smiles: string;
  formula: string;
  molecular_weight: number;
  xlogp: number | null;
  tpsa: number | null;
  hbond_donors: number;
  hbond_acceptors: number;
  rotatable_bonds: number;
  heavy_atoms: number;
  has_3d: boolean;
  conformer_source: "pubchem" | "rdkit" | null;
  source: string;
  source_url: string;
};

/** A supported name close to an unsupported one: the scope name or alias, and its drug. */
export type Suggestion = {
  alias: string;
  cid: number;
  name: string;
};

export type Resolution = {
  query: string;
  status: "found" | "not_supported";
  compound: Compound | null;
  matched_alias: string | null;
  match_kind: "name" | "alias" | "pubchem" | "brand" | null;
  suggestions: Suggestion[];
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

/** Which supported drug a name refers to; an unsupported name comes with close supported names. */
export function resolveDrug(name: string, signal?: AbortSignal): Promise<Resolution> {
  return getJson<Resolution>(`/drugs/resolve?name=${encodeURIComponent(name)}`, signal);
}
