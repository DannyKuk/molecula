import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from molecula.agent.llm import (
    LLMConfigError,
    LocalChatOpenAI,
    chat_model_name,
    get_answer_model,
    get_chat_model,
    get_source_check_model,
)
from molecula.config import Settings

LLM_FIELDS: dict[str, Any] = {
    "openrouter_api_key": None,
    "llm_model": None,
    "local_llm_base_url": None,
    "local_llm_model": None,
    "llm_reasoning_effort": None,
    "answer_reasoning_effort": "medium",
    "source_check_reasoning_effort": "medium",
    "offline": False,
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


def both_setups(**overrides: Any) -> Settings:
    """An OpenRouter key and a local server, as a `.env` with both setups holds them."""
    return openrouter_settings(
        local_llm_base_url="http://localhost:11434/v1", local_llm_model="qwen3:8b", **overrides
    )


def test_offline_the_local_server_answers() -> None:
    model = chat_openai(both_setups(offline=True))

    assert model.openai_api_base == "http://localhost:11434/v1"
    assert model.model_name == "qwen3:8b"
    assert not model.default_headers


def test_online_with_a_key_openrouter_answers_although_a_local_server_is_set() -> None:
    model = chat_openai(both_setups(offline=False))

    assert model.openai_api_base == "https://openrouter.ai/api/v1"
    assert model.model_name == "openai/gpt-4o-mini"


def test_offline_without_a_local_server_never_falls_back_to_openrouter() -> None:
    with pytest.raises(LLMConfigError, match="OFFLINE=1 needs a local chat model"):
        get_chat_model(openrouter_settings(offline=True))


def test_the_chat_model_name_follows_the_same_rule() -> None:
    assert chat_model_name(both_setups(offline=True)) == "qwen3:8b"
    assert chat_model_name(both_setups(offline=False)) == "openai/gpt-4o-mini"
    assert chat_model_name(settings()) == "unknown"


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


def test_reasoning_effort_reaches_the_request() -> None:
    model = chat_openai(local_settings(llm_reasoning_effort="medium"))

    assert model._default_params["reasoning_effort"] == "medium"


def test_without_a_reasoning_effort_the_request_leaves_it_to_the_model() -> None:
    model = chat_openai(local_settings())

    assert "reasoning_effort" not in model._default_params


def test_the_answering_agent_reasons_at_its_own_effort() -> None:
    model = get_answer_model(local_settings(answer_reasoning_effort="high"))

    assert isinstance(model, ChatOpenAI)
    assert model._default_params["reasoning_effort"] == "high"
    assert model.model_name == "qwen3:8b"


def test_the_answers_reason_at_medium_while_the_other_calls_keep_the_models_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("LLM_REASONING_EFFORT", "ANSWER_REASONING_EFFORT"):
        monkeypatch.delenv(name, raising=False)
    defaults = {
        name: value
        for name, value in LLM_FIELDS.items()
        if name not in ("llm_reasoning_effort", "answer_reasoning_effort")
    }
    plain = Settings(
        _env_file=None,
        **(defaults | {"local_llm_base_url": "http://localhost:1234/v1", "local_llm_model": "m"}),
    )
    answer_model = get_answer_model(plain)
    chat_model = get_chat_model(plain)

    assert isinstance(answer_model, ChatOpenAI)
    assert isinstance(chat_model, ChatOpenAI)
    assert answer_model._default_params["reasoning_effort"] == "medium"
    assert "reasoning_effort" not in chat_model._default_params


def test_an_answer_effort_of_default_leaves_it_to_the_model() -> None:
    model = get_answer_model(local_settings(answer_reasoning_effort="default"))

    assert isinstance(model, ChatOpenAI)
    assert "reasoning_effort" not in model._default_params


def test_the_source_check_reasons_at_its_own_effort() -> None:
    model = get_source_check_model(
        local_settings(llm_reasoning_effort="low", source_check_reasoning_effort="high")
    )

    assert isinstance(model, ChatOpenAI)
    assert model._default_params["reasoning_effort"] == "high"
    assert model.model_name == "qwen3:8b"


def test_a_source_check_effort_of_default_leaves_it_to_the_model() -> None:
    model = get_source_check_model(local_settings(source_check_reasoning_effort="default"))

    assert isinstance(model, ChatOpenAI)
    assert "reasoning_effort" not in model._default_params


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


def chunk(delta: dict[str, Any], finish_reason: str | None = None) -> str:
    body = {
        "id": "chatcmpl-1",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "openai/gpt-oss-20b",
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    return f"data: {json.dumps(body)}\n\n"


class LocalServer:
    """Stands in for LM Studio: streams `reply` and keeps the request bodies it was sent."""

    def __init__(self, reply: list[str]) -> None:
        self.reply = reply
        self.requests: list[dict[str, Any]] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        body = "".join(self.reply) + "data: [DONE]\n\n"
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    def model(self) -> LocalChatOpenAI:
        return LocalChatOpenAI(
            base_url="http://localhost:1234/v1",
            api_key=SecretStr("local"),
            model="openai/gpt-oss-20b",
            streaming=True,
            http_client=httpx.Client(transport=httpx.MockTransport(self.handle)),
        )

    def sent_assistant_messages(self) -> list[dict[str, Any]]:
        return [m for m in self.requests[-1]["messages"] if m["role"] == "assistant"]


def test_a_local_server_gets_the_model_that_keeps_reasoning() -> None:
    assert isinstance(get_chat_model(local_settings()), LocalChatOpenAI)
    assert not isinstance(get_chat_model(openrouter_settings()), LocalChatOpenAI)


def tool_call(call_id: str, content: str = "") -> AIMessage:
    return AIMessage(
        content=content,
        tool_calls=[{"name": "lookup", "args": {"drug": "aspirin"}, "id": call_id}],
    )


def lookup(call_id: str, content: str = "") -> list[BaseMessage]:
    return [tool_call(call_id, content), ToolMessage("aspirin: NSAID", tool_call_id=call_id)]


def sent_messages(server: LocalServer) -> list[tuple[str, str | None]]:
    return [(sent["role"], sent.get("content")) for sent in server.requests[-1]["messages"]]


def test_earlier_tool_calls_go_back_as_one_message_of_results_after_the_question() -> None:
    server = LocalServer([chunk({"role": "assistant", "content": "Both are NSAIDs."})])

    server.model().invoke(
        [
            HumanMessage("What is aspirin?"),
            AIMessage("Aspirin relieves pain."),
            HumanMessage("What are aspirin and ibuprofen?"),
            *lookup("call_1"),
            *lookup("call_2"),
        ]
    )

    sent = sent_messages(server)
    assert [role for role, _ in sent] == ["user", "assistant", "user", "user"]
    assert sent[1] == ("assistant", "Aspirin relieves pain.")
    results = sent[3][1] or ""
    assert results.count('<result call="lookup({"drug": "aspirin"})">') == 2
    assert results.count("aspirin: NSAID") == 2
    assert all("tool_calls" not in m for m in server.requests[-1]["messages"])


def test_a_request_without_tool_calls_goes_unchanged() -> None:
    server = LocalServer([chunk({"role": "assistant", "content": "Aspirin is an NSAID."})])

    server.model().invoke([HumanMessage("What is aspirin?")])

    assert sent_messages(server) == [("user", "What is aspirin?")]
