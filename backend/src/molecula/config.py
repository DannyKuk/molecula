from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
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
    embedding_model: str = "local"
    openfda_api_key: SecretStr | None = None
    offline: bool = False
    data_dir: Path = REPO_ROOT / "data"

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
