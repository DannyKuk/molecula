from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/src/molecula/config.py -> the repo root, where .env and data/ live in a local checkout.
# Inside Docker the package is installed elsewhere, so compose sets DATA_DIR and passes .env in.
REPO_ROOT = Path(__file__).resolve().parents[3]

# Shared by the chat model (agent/llm.py) and the cloud embeddings (rag/embeddings.py).
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_ATTRIBUTION_HEADERS = {
    "HTTP-Referer": "https://github.com/DannyKuk/molecula",
    "X-OpenRouter-Title": "Molecula",
}
# EMBEDDING_MODEL's value for the local sentence-transformers model; anything else names a cloud
# model on OpenRouter.
LOCAL_EMBEDDINGS = "local"
# The section-group boost chosen for bge-m3 on the retrieval questions (#112). A cloud model gets
# none: with gemini-embedding-2 the boost only cost recall (#96).
LOCAL_SECTION_GROUP_BOOST = 0.15


class Settings(BaseSettings):
    """App settings, read from the environment and the repo's `.env` (keys as in `.env.example`)."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    openrouter_api_key: SecretStr | None = None
    # Measured against gpt-oss-20b and claude-haiku-5.5 in docs/decisions/chat-model.md (#98).
    llm_model: str | None = "openai/gpt-6-luna"
    local_llm_base_url: str | None = None
    local_llm_model: str | None = None
    llm_temperature: float = 0.2
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2
    # The effort of the guard's sorting and the label-filter extraction. Empty leaves the model's
    # own default: gpt-oss-20b in LM Studio then reasons about as briefly as on "low", gpt-5-mini
    # on OpenRouter longer than on "medium" (#193, #198).
    llm_reasoning_effort: Literal["low", "medium", "high"] | None = None
    # The answering agent's own effort: at gpt-oss-20b's default it stopped after the 3D view or
    # the properties and wrote the rest of a comparison from memory (#254). "default" leaves the
    # model's own default.
    answer_reasoning_effort: Literal["default", "low", "medium", "high"] = "medium"
    # The source check's own effort, so the writer keeps its fast default (#206, #213).
    # "default" leaves the model's own default, as an empty LLM_REASONING_EFFORT does.
    source_check_reasoning_effort: Literal["default", "low", "medium", "high"] = "medium"
    # A decision model answers typed questions with probabilities over `/v1/systemone` (#102):
    # Jev on OpenRouter, or a model loaded in LM Studio when LOCAL_DECISION_BASE_URL is set.
    # Online, it sorts each message for the guard: as accurate as the chat model on the safety
    # set and about five times faster (#226).
    decision_model: str | None = "jev-1.13"
    local_decision_base_url: str | None = None
    decision_timeout_seconds: Annotated[float, Field(gt=0)] = 10.0
    # A cloud model id becomes a folder name under index/cloud/, so no backslashes or colons.
    embedding_model: Annotated[str, Field(pattern=r"^[A-Za-z0-9._/-]+$")] = LOCAL_EMBEDDINGS
    # Multilingual and among the best CPU-sized models in docs/decisions/embeddings.md (#88).
    local_embedding_model: str = "BAAI/bge-m3"
    # The Hugging Face commit of LOCAL_EMBEDDING_MODEL that the published index was built with;
    # `ingest fetch` downloads it and checks its weights (#118).
    local_embedding_model_revision: Annotated[str, Field(pattern=r"^[0-9a-f]{40}$")] = (
        "5617a9f61b028005a4858fdac845db406aefb181"
    )
    retrieval_top_k: Annotated[int, Field(ge=1, le=50)] = 5
    retrieval_min_score: Annotated[float, Field(ge=-1.0, le=1.0)] = 0.0
    # Added to the cosine similarity of a chunk in the extracted section groups. Empty takes the
    # embedding model's value (section_group_boost); re-measure when the embeddings or ranking
    # change (#112).
    retrieval_section_group_boost: Annotated[float | None, Field(ge=0.0, le=2.0)] = None
    # "hybrid" adds BM25 keyword search to the embeddings, merged by reciprocal rank fusion (#44).
    retrieval_mode: Literal["dense", "bm25", "hybrid"] = "dense"
    # Model calls per answer; the last one gets no tools, so the agent answers (#124).
    chat_max_steps: Annotated[int, Field(ge=1, le=20)] = 8
    chat_timeout_seconds: Annotated[float, Field(gt=0)] = 180.0
    # "mcp" gives the agent its tools through the MCP server in molecula.mcp, so the chat runs
    # through the same server any MCP client uses (#42).
    agent_tools: Literal["local", "mcp"] = "local"
    # Questions per client (by IP) to POST /chat, and what the cloud models may cost per UTC day,
    # so a public instance can't run up the OpenRouter bill (#39).
    chat_requests_per_minute: Annotated[int, Field(ge=1)] = 10
    chat_requests_per_day: Annotated[int, Field(ge=1)] = 200
    daily_cost_limit_usd: Annotated[float, Field(gt=0)] = 2.0
    # Read the client's IP from X-Forwarded-For, which only a proxy in front may set.
    trust_proxy: bool = False
    openfda_api_key: SecretStr | None = None
    # The backend updates the labels every day at this UTC hour, unless LABEL_UPDATE_SCHEDULE=0
    # (e.g. a store kept as the eval baseline) or OFFLINE=1 (#342).
    label_update_schedule: bool = True
    label_update_hour: Annotated[int, Field(ge=0, le=23)] = 3
    # The dashboard's Update now button and its route, POST /labels/update; off answers 404.
    label_update_button: bool = False
    offline: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    # The GitHub release `ingest fetch` downloads the store from (#35); a new snapshot bumps it.
    store_release: Annotated[str, Field(pattern=r"^store-\d{4}-\d{2}-\d{2}$")] = "store-2026-10-16"
    data_dir: Path = REPO_ROOT / "data"
    cors_origins: list[str] = ["http://localhost:3000"]
    name_suggestion_cutoff: Annotated[float, Field(ge=0.0, le=1.0)] = 0.8

    @property
    def section_group_boost(self) -> float:
        """RETRIEVAL_SECTION_GROUP_BOOST, or when it is empty 0.15 for the local model and 0 for
        a cloud model."""
        if self.retrieval_section_group_boost is not None:
            return self.retrieval_section_group_boost
        if self.embedding_model == LOCAL_EMBEDDINGS:
            return LOCAL_SECTION_GROUP_BOOST
        return 0.0

    @property
    def build_dir(self) -> Path:
        """Where the ingest steps write the built store (SQLite, structures, index)."""
        return self.data_dir / "build"

    @property
    def usage_db_path(self) -> Path:
        """The usage log (#334): what the app records while it runs, kept out of the built
        store so a new snapshot replaces the store without touching it and never ships it."""
        return self.data_dir / "runtime" / "usage.db"

    @property
    def scope_path(self) -> Path:
        return self.data_dir / "scope.yaml"

    @property
    def db_path(self) -> Path:
        return self.build_dir / "molecula.db"

    @property
    def conformers_dir(self) -> Path:
        return self.build_dir / "structures" / "compounds"

    @property
    def complexes_dir(self) -> Path:
        return self.build_dir / "structures" / "complexes"

    @property
    def hero_set_path(self) -> Path:
        return self.data_dir / "hero_set.yaml"

    @property
    def local_index_dir(self) -> Path:
        """The local model's label index, the one store releases ship."""
        return self.build_dir / "index" / "chroma"

    @property
    def index_dir(self) -> Path:
        """The label index of EMBEDDING_MODEL. A cloud model's index sits next to the local one,
        so the local index keeps the path store releases unpack to (#96)."""
        if self.embedding_model == LOCAL_EMBEDDINGS:
            return self.local_index_dir
        return (
            self.build_dir / "index" / "cloud" / self.embedding_model.replace("/", "--") / "chroma"
        )

    @property
    def keyword_index_path(self) -> Path:
        return self.build_dir / "index" / "bm25.db"

    @property
    def models_dir(self) -> Path:
        """Local model weights, saved when the index is built so the app runs with OFFLINE=1."""
        return self.build_dir / "models"

    @property
    def store_release_url(self) -> str:
        """Where the assets of the pinned store release are downloaded from."""
        return f"https://github.com/DannyKuk/molecula/releases/download/{self.store_release}"

    @property
    def export_dir(self) -> Path:
        """Where `ingest export` writes the store archive and its manifest for a release."""
        return self.build_dir / "export"


@lru_cache
def get_settings() -> Settings:
    return Settings()
