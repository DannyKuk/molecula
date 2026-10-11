from pathlib import Path

import pytest

from molecula.config import Settings

ENV_KEYS = [
    "OPENROUTER_API_KEY",
    "LLM_MODEL",
    "LOCAL_LLM_BASE_URL",
    "LOCAL_LLM_MODEL",
    "EMBEDDING_MODEL",
    "OPENFDA_API_KEY",
    "OFFLINE",
    "DATA_DIR",
]


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def write_env(tmp_path: Path, content: str) -> Path:
    env_file = tmp_path / ".env"
    env_file.write_text(content, encoding="utf-8")
    return env_file


def test_reads_values_from_env_file(tmp_path: Path) -> None:
    env_file = write_env(
        tmp_path,
        "OPENROUTER_API_KEY=sk-test\nLLM_MODEL=some/model\nOFFLINE=1\nDATA_DIR=/srv/data\n",
    )

    settings = Settings(_env_file=env_file)

    assert settings.openrouter_api_key is not None
    assert settings.openrouter_api_key.get_secret_value() == "sk-test"
    assert settings.llm_model == "some/model"
    assert settings.offline is True
    assert settings.build_dir == Path("/srv/data/build")
    assert settings.db_path == Path("/srv/data/build/molecula.db")


@pytest.mark.parametrize(("raw", "expected"), [("1", True), ("0", False), ("true", True)])
def test_offline_flag_parses_to_bool(
    raw: str, expected: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OFFLINE", raw)

    assert Settings(_env_file=None).offline is expected


def test_copied_env_example_loads_with_empty_keys(tmp_path: Path) -> None:
    example = Path(__file__).resolve().parents[2] / ".env.example"
    env_file = write_env(tmp_path, example.read_text(encoding="utf-8"))

    settings = Settings(_env_file=env_file)

    assert settings.openrouter_api_key is None
    assert settings.local_llm_base_url is None
    assert settings.embedding_model == "local"
    assert settings.offline is False


def test_missing_env_file_uses_defaults(tmp_path: Path) -> None:
    settings = Settings(_env_file=tmp_path / "does-not-exist.env")

    assert settings.llm_model is None
    assert settings.openfda_api_key is None
    assert settings.offline is False
    assert settings.build_dir == settings.data_dir / "build"
