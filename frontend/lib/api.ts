export const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type HealthResponse = {
  status: "ok";
};

/** The model that writes the answers (`ChatModel` in `backend/src/molecula/schemas/chat.py`). */
export type ChatModel = {
  name: string;
  local: boolean;
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

export type Xyz = [number, number, number];

export type Residue = { chain: string; number: number; ins_code: string; name: string };

export type Atom = { name: string; element: string; xyz: Xyz };

/** A ligand or cofactor copy with its heavy atoms and bonds. */
export type Molecule = {
  code: string;
  chain: string;
  number: number;
  atoms: Atom[];
  bonds: { atoms: [number, number]; order: "single" | "double" | "triple" | "aromatic" }[];
};

/** A drug-target complex for the 3D view (`Complex` in `backend/src/molecula/schemas/complexes.py`):
 * heavy atoms only, coordinates in Å. */
export type Complex = {
  pdb_id: string;
  ligand: Molecule;
  /** One point per residue: the CA atom of an amino acid, the P atom of a nucleotide (`sse` null). */
  trace: (Residue & { sse: "helix" | "sheet" | "coil" | null; xyz: Xyz })[];
  pocket: (Residue & { atoms: Atom[] })[];
  /** The metal ions within coordination distance of the drug, and the cofactors it binds through;
   * their contacts are in `contacts`. */
  metals: (Residue & { element: string; xyz: Xyz })[];
  cofactors: Molecule[];
  contacts: {
    kind: "hbond" | "coordination" | "contact";
    residue: Residue;
    residue_atom: string;
    ligand_atom: number;
    distance: number;
  }[];
  target: string | null;
  organism: string | null;
  caption: string | null;
  showcase: boolean;
  source_url: string;
};

export type Outcome = "answered" | "error" | "stopped" | "limited";

export type InputCategory =
  | "ok"
  | "overdose_emergency"
  | "personal_medical_advice"
  | "lethal_dose"
  | "synthesis_or_misuse"
  | "prompt_injection"
  | "off_topic";

export type ErrorKind =
  "input_check_failed" | "model_error" | "timeout" | "no_answer" | "server_error";

/** One UTC day of chat requests (`UsageDay` in `backend/src/molecula/schemas/stats.py`). */
export type UsageDay = {
  date: string;
  requests: number;
  outcomes: Partial<Record<Outcome, number>>;
  latency_p50_ms: number | null;
  latency_p95_ms: number | null;
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
};

/** What the store holds and how the chat was used (`Stats` in `backend/src/molecula/schemas/stats.py`). */
export type Stats = {
  knowledge_base: {
    drugs: number;
    labels: number;
    label_sections: number;
    chunks: number;
    targets: number;
    conformers: number;
    complexes: number;
    schema_version: number;
    labels_fetched_from: string | null;
    labels_fetched_to: string | null;
  };
  usage: {
    days: UsageDay[];
    tool_calls: Record<string, number>;
    categories: Partial<Record<InputCategory, number>>;
    errors: Partial<Record<ErrorKind, number>>;
  };
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

async function get(path: string, signal?: AbortSignal): Promise<Response> {
  const response = await fetch(`${API_URL}${path}`, { signal });
  if (!response.ok) {
    throw new ApiError(path, response.status);
  }
  return response;
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  return (await (await get(path, signal)).json()) as T;
}

export function getHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return getJson<HealthResponse>("/health", signal);
}

/** The model that writes the answers; fails with 503 while the chat is off. */
export function getChatModel(signal?: AbortSignal): Promise<ChatModel> {
  return getJson<ChatModel>("/chat/model", signal);
}

/** Every drug in the store, sorted by name. */
export function getDrugs(signal?: AbortSignal): Promise<Drug[]> {
  return getJson<Drug[]>("/drugs", signal);
}

/** Which supported drug a name refers to; an unsupported name comes with close supported names. */
export function resolveDrug(name: string, signal?: AbortSignal): Promise<Resolution> {
  return getJson<Resolution>(`/drugs/resolve?name=${encodeURIComponent(name)}`, signal);
}

/** A drug's 3D conformer as SDF text; a 404 means the drug has none. */
export async function getStructure(cid: number, signal?: AbortSignal): Promise<string> {
  return (await get(`/drugs/${cid}/structure`, signal)).text();
}

/** A drug's reviewed complex with its target; a 404 means it has none. */
export function getComplex(cid: number, signal?: AbortSignal): Promise<Complex> {
  return getJson<Complex>(`/drugs/${cid}/complex`, signal);
}

/** What the store holds, and the chat's use over the last `days` UTC days (1–365). */
export function getStats(days: number, signal?: AbortSignal): Promise<Stats> {
  return getJson<Stats>(`/stats?days=${days}`, signal);
}
