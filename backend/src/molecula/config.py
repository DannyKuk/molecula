from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/src/molecula/config.py -> the repo root, where .env and data/ live in a local checkout.
# Inside Docker the package is installed elsewhere, so compose sets DATA_DIR and passes .env in.
REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """App settings, read from the environment and the repo's `.env` (keys as in `.env.example`)."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    openrouter_api_key: SecretStr | None = None
    llm_model: str | None = None
    local_llm_base_url: str | None = None
    local_llm_model: str | None = None
    llm_temperature: float = 0.2
    llm_timeout_seconds: float = 60.0
    llm_max_retries: int = 2
    embedding_model: str = "local"
    local_embedding_model: str = "BAAI/bge-small-en-v1.5"
    openfda_api_key: SecretStr | None = None
    offline: bool = False
    data_dir: Path = REPO_ROOT / "data"
    cors_origins: list[str] = ["http://localhost:3000"]
    name_suggestion_cutoff: Annotated[float, Field(ge=0.0, le=1.0)] = 0.8

    @property
    def build_dir(self) -> Path:
        """Where the ingest steps write the built store (SQLite, structures, index)."""
        return self.data_dir / "build"

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
    def index_dir(self) -> Path:
        return self.build_dir / "index" / "chroma"

    @property
    def models_dir(self) -> Path:
        """Local model weights, saved when the index is built so the app runs with OFFLINE=1."""
        return self.build_dir / "models"


@lru_cache
def get_settings() -> Settings:
    return Settings()
