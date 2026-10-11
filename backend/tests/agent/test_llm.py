from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from molecula.agent.llm import LLMConfigError, get_chat_model
from molecula.config import Settings

LLM_FIELDS: dict[str, Any] = {
    "openrouter_api_key": None,
    "llm_model": None,
    "local_llm_base_url": None,
    "local_llm_model": None,
}


def settings(**overrides: Any) -> Settings:
    """Settings with every LLM field given, so the machine's environment can't leak in."""
    return Settings(_env_file=None, **(LLM_FIELDS | overrides))


def openrouter_settings(**overrides: Any) -> Settings:
    return settings(
        openrouter_api_key=SecretStr("sk-or-test"), llm_model="openai/gpt-4o-mini", **overrides
    )


def local_settings(**overrides: Any) -> Settings:
    return settings(
        local_llm_base_url="http://localhost:11434/v1", local_llm_model="qwen3:8b", **overrides
    )


def chat_openai(settings: Settings) -> ChatOpenAI:
    model = get_chat_model(settings)
    assert isinstance(model, ChatOpenAI)
    return model


def test_openrouter_settings_build_an_openrouter_client() -> None:
    model = chat_openai(openrouter_settings())

    assert model.openai_api_base == "https://openrouter.ai/api/v1"
    assert model.model_name == "openai/gpt-4o-mini"
    assert isinstance(model.openai_api_key, SecretStr)
    assert model.openai_api_key.get_secret_value() == "sk-or-test"


def test_openrouter_requests_carry_the_attribution_headers() -> None:
    model = chat_openai(openrouter_settings())

    expected = {
        "HTTP-Referer": "https://github.com/DannyKuk/molecula",
        "X-OpenRouter-Title": "Molecula",
    }
    assert model.default_headers == expected
    assert expected.items() <= model.root_client.default_headers.items()
    assert str(model.root_client.base_url) == "https://openrouter.ai/api/v1/"


def test_local_base_url_wins_over_openrouter() -> None:
    model = chat_openai(
        openrouter_settings(
            local_llm_base_url="http://localhost:11434/v1", local_llm_model="qwen3:8b"
        )
    )

    assert model.openai_api_base == "http://localhost:11434/v1"
    assert model.model_name == "qwen3:8b"
    assert not model.default_headers


def test_local_server_needs_no_api_key() -> None:
    model = chat_openai(
        settings(local_llm_base_url="http://localhost:1234/v1", local_llm_model="local-model")
    )

    assert model.openai_api_base == "http://localhost:1234/v1"
    assert isinstance(model.openai_api_key, SecretStr)
    assert model.openai_api_key.get_secret_value()


@pytest.mark.parametrize("build", [openrouter_settings, local_settings])
def test_streams_and_reports_token_usage(build: Callable[[], Settings]) -> None:
    model = chat_openai(build())

    assert model.streaming is True
    assert model.stream_usage is True


def test_temperature_timeout_and_retries_come_from_settings() -> None:
    model = chat_openai(
        openrouter_settings(llm_temperature=0.0, llm_timeout_seconds=15.0, llm_max_retries=5)
    )

    assert model.temperature == 0.0
    assert model.request_timeout == 15.0
    assert model.max_retries == 5


def test_missing_key_without_a_local_server_names_the_settings_to_fill_in() -> None:
    with pytest.raises(LLMConfigError) as error:
        get_chat_model(settings(llm_model="openai/gpt-4o-mini"))

    message = str(error.value)
    for name in ("OPENROUTER_API_KEY", "LLM_MODEL", "LOCAL_LLM_BASE_URL", "LOCAL_LLM_MODEL"):
        assert name in message


def test_openrouter_key_without_a_model_is_an_error() -> None:
    with pytest.raises(LLMConfigError, match="LLM_MODEL is empty"):
        get_chat_model(settings(openrouter_api_key=SecretStr("sk-or-test")))


def test_local_server_without_a_model_is_an_error() -> None:
    with pytest.raises(LLMConfigError, match="LOCAL_LLM_MODEL is empty"):
        get_chat_model(settings(local_llm_base_url="http://localhost:11434/v1"))


def test_settings_read_from_env_file_reach_the_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in (
        "OPENROUTER_API_KEY",
        "LLM_MODEL",
        "LOCAL_LLM_BASE_URL",
        "LOCAL_LLM_MODEL",
        "LLM_TEMPERATURE",
    ):
        monkeypatch.delenv(key, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LOCAL_LLM_BASE_URL=http://localhost:11434/v1\nLOCAL_LLM_MODEL=llama3.2\nLLM_TEMPERATURE=0.7\n",
        encoding="utf-8",
    )

    model = chat_openai(Settings(_env_file=env_file))

    assert (model.openai_api_base, model.model_name, model.temperature) == (
        "http://localhost:11434/v1",
        "llama3.2",
        0.7,
    )
