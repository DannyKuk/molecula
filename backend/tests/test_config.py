import re
from pathlib import Path

import pytest
from pydantic import ValidationError

from molecula.config import Settings

ENV_EXAMPLE = Path(__file__).resolve().parents[2] / ".env.example"
ENV_KEYS = [name.upper() for name in Settings.model_fields]
# A setting as `KEY=value`, or as `# KEY=value` for one left at its default.
SETTING_LINE = re.compile(r"^(# )?([A-Z_]+)=(\S*)$")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def example_settings() -> list[tuple[str, str, bool]]:
    """Each setting in .env.example as (key, value, commented out)."""
    lines = ENV_EXAMPLE.read_text(encoding="utf-8").splitlines()
    matches = [SETTING_LINE.match(line) for line in lines]
    return [(m[2], m[3], m[1] is not None) for m in matches if m]


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


def test_cors_origins_default_to_the_local_frontend_and_parse_from_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert Settings(_env_file=None).cors_origins == ["http://localhost:3000"]

    monkeypatch.setenv("CORS_ORIGINS", '["https://molecula.example", "http://localhost:3001"]')

    assert Settings(_env_file=None).cors_origins == [
        "https://molecula.example",
        "http://localhost:3001",
    ]


def test_copied_env_example_runs_the_local_model_from_docker(tmp_path: Path) -> None:
    env_file = write_env(tmp_path, ENV_EXAMPLE.read_text(encoding="utf-8"))

    settings = Settings(_env_file=env_file)

    assert settings.openrouter_api_key is None
    assert settings.offline is False
    assert settings.local_llm_base_url == "http://host.docker.internal:1234/v1"
    assert settings.local_llm_model == "openai/gpt-oss-20b"
    assert settings.model_dump(exclude={"local_llm_base_url", "local_llm_model"}) == Settings(
        _env_file=None
    ).model_dump(exclude={"local_llm_base_url", "local_llm_model"})


def test_env_example_names_every_setting_once() -> None:
    keys = [key for key, _, _ in example_settings()]

    assert sorted(keys) == sorted(ENV_KEYS)


@pytest.mark.parametrize(
    ("key", "value"), [(key, value) for key, value, commented in example_settings() if commented]
)
def test_env_example_shows_the_default_of_a_commented_setting(
    tmp_path: Path, key: str, value: str
) -> None:
    env_file = write_env(tmp_path, f"{key}={value}\n")
    field = key.lower()

    assert getattr(Settings(_env_file=env_file), field) == getattr(Settings(_env_file=None), field)


@pytest.mark.parametrize("raw", ["-0.1", "1.5"])
def test_name_suggestion_cutoff_outside_0_to_1_is_rejected(
    raw: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NAME_SUGGESTION_CUTOFF", raw)

    with pytest.raises(ValidationError, match="name_suggestion_cutoff"):
        Settings(_env_file=None)


def test_missing_env_file_uses_defaults(tmp_path: Path) -> None:
    settings = Settings(_env_file=tmp_path / "does-not-exist.env")

    assert settings.llm_model == "openai/gpt-6-luna"
    assert settings.openfda_api_key is None
    assert settings.offline is False
    assert settings.build_dir == settings.data_dir / "build"


def test_cloud_embedding_model_gets_an_index_next_to_the_local_one(tmp_path: Path) -> None:
    local = Settings(_env_file=None, data_dir=tmp_path)
    cloud = Settings(
        _env_file=None, data_dir=tmp_path, embedding_model="openai/text-embedding-3-large"
    )

    assert local.index_dir == tmp_path / "build" / "index" / "chroma"
    assert cloud.local_index_dir == local.index_dir
    assert cloud.index_dir == (
        tmp_path / "build" / "index" / "cloud" / "openai--text-embedding-3-large" / "chroma"
    )


@pytest.mark.parametrize("model", ["openai\text-embedding-3-large", "c:model", ""])
def test_embedding_model_that_cant_be_a_folder_name_is_rejected(tmp_path: Path, model: str) -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, data_dir=tmp_path, embedding_model=model)


def test_section_group_boost_follows_the_embedding_model(tmp_path: Path) -> None:
    local = Settings(_env_file=None, data_dir=tmp_path)
    cloud = Settings(_env_file=None, data_dir=tmp_path, embedding_model="google/gemini-embedding-2")

    assert (local.section_group_boost, cloud.section_group_boost) == (0.15, 0.0)


@pytest.mark.parametrize("model", ["local", "google/gemini-embedding-2"])
def test_set_section_group_boost_wins_over_the_models(tmp_path: Path, model: str) -> None:
    env_file = write_env(tmp_path, "RETRIEVAL_SECTION_GROUP_BOOST=0.08\n")

    settings = Settings(_env_file=env_file, data_dir=tmp_path, embedding_model=model)

    assert settings.section_group_boost == 0.08


def test_empty_section_group_boost_takes_the_models(tmp_path: Path) -> None:
    env_file = write_env(
        tmp_path, "EMBEDDING_MODEL=google/gemini-embedding-2\nRETRIEVAL_SECTION_GROUP_BOOST=\n"
    )

    assert Settings(_env_file=env_file, data_dir=tmp_path).section_group_boost == 0.0
