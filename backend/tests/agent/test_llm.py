import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx
import pytest
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, SecretStr

from molecula.agent.llm import (
    LLMConfigError,
    LocalChatOpenAI,
    PricedChatOpenAI,
    chat_model_name,
    cloud_model_choices,
    get_answer_model,
    get_chat_model,
    get_source_check_model,
    local_model_names,
)
from molecula.config import Settings
from molecula.schemas.chat import ChatModel
from molecula.schemas.usage import usage_of

FIXTURES = Path(__file__).parents[1] / "fixtures" / "openrouter"

LLM_FIELDS: dict[str, Any] = {
    "openrouter_api_key": None,
    "llm_model": None,
    "llm_models": [],
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


def test_a_picked_local_model_answers_on_the_local_server() -> None:
    model = get_answer_model(both_setups(), ChatModel(name="google/gemma-4-31b", local=True))

    assert isinstance(model, LocalChatOpenAI)
    assert model.openai_api_base == "http://localhost:11434/v1"
    assert model.model_name == "google/gemma-4-31b"
    assert model.reasoning_effort == "medium"


def test_a_picked_cloud_model_answers_on_openrouter() -> None:
    model = get_answer_model(
        both_setups(), ChatModel(name="anthropic/claude-haiku-5.5", local=False)
    )

    assert isinstance(model, ChatOpenAI)
    assert not isinstance(model, LocalChatOpenAI)
    assert model.openai_api_base == "https://openrouter.ai/api/v1"
    assert model.model_name == "anthropic/claude-haiku-5.5"


def test_a_picked_local_model_runs_the_checks_on_the_local_server_at_their_own_effort() -> None:
    gemma = ChatModel(name="google/gemma-4-31b", local=True)
    settings = both_setups(llm_reasoning_effort="low", source_check_reasoning_effort="high")

    checks = get_chat_model(settings, gemma)
    source_check = get_source_check_model(settings, gemma)

    assert isinstance(checks, LocalChatOpenAI)
    assert isinstance(source_check, LocalChatOpenAI)
    assert checks.openai_api_base == source_check.openai_api_base == "http://localhost:11434/v1"
    assert checks.model_name == source_check.model_name == "google/gemma-4-31b"
    assert checks.reasoning_effort == "low"
    assert source_check.reasoning_effort == "high"


def test_a_picked_local_model_without_a_local_server_is_an_error() -> None:
    with pytest.raises(LLMConfigError, match="LOCAL_LLM_BASE_URL is empty"):
        get_answer_model(openrouter_settings(), ChatModel(name="qwen3:8b", local=True))


def test_the_cloud_choices_are_llm_model_and_llm_models_once_each() -> None:
    choices = cloud_model_choices(
        openrouter_settings(llm_models=["anthropic/claude-haiku-5.5", "openai/gpt-4o-mini"])
    )

    assert choices == [
        ChatModel(name="openai/gpt-4o-mini", local=False),
        ChatModel(name="anthropic/claude-haiku-5.5", local=False),
    ]


def test_there_are_no_cloud_choices_offline_or_without_a_key() -> None:
    assert cloud_model_choices(both_setups(offline=True, llm_models=["openai/gpt-6"])) == []
    assert cloud_model_choices(local_settings(llm_models=["openai/gpt-6"])) == []


def models_server(handle: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handle))


def listed_by_local_server(
    settings: Settings, handle: Callable[[httpx.Request], httpx.Response]
) -> list[str]:
    return asyncio.run(local_model_names(settings, models_server(handle)))


def lm_studio_models(request: httpx.Request) -> httpx.Response:
    assert request.url == "http://localhost:11434/v1/models"
    ids = ["openai/gpt-oss-20b", "google/gemma-4-31b", "text-embedding-nomic-embed-text-v1.5"]
    return httpx.Response(200, json={"object": "list", "data": [{"id": id} for id in ids]})


def test_the_local_server_lists_its_chat_models_without_the_embedding_models() -> None:
    assert listed_by_local_server(local_settings(), lm_studio_models) == [
        "openai/gpt-oss-20b",
        "google/gemma-4-31b",
    ]


def test_a_local_server_that_is_down_lists_no_models() -> None:
    def down(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused", request=request)

    assert listed_by_local_server(local_settings(), down) == []


def test_without_a_local_server_there_is_no_local_list_to_read() -> None:
    def unexpected(request: httpx.Request) -> httpx.Response:
        raise AssertionError("no request expected")

    assert listed_by_local_server(openrouter_settings(), unexpected) == []


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


def usage_chunk(**usage: Any) -> str:
    """The last chunk of a stream, with the usage and no choices."""
    body = {
        "id": "chatcmpl-1",
        "object": "chat.completion.chunk",
        "created": 0,
        "model": "openai/gpt-oss-20b",
        "choices": [],
        "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120, **usage},
    }
    return f"data: {json.dumps(body)}\n\n"


class LocalServer:
    """Stands in for LM Studio, or OpenRouter: streams `reply` and keeps the request bodies it
    was sent."""

    def __init__(self, reply: list[str]) -> None:
        self.reply = reply
        self.requests: list[dict[str, Any]] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(json.loads(request.content))
        body = "".join(self.reply) + "data: [DONE]\n\n"
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    def model(self, model_class: type[PricedChatOpenAI] = LocalChatOpenAI) -> PricedChatOpenAI:
        return model_class(
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


def test_a_request_without_a_user_message_goes_unchanged() -> None:
    server = LocalServer([chunk({"role": "assistant", "content": "Hello."})])

    server.model().invoke([SystemMessage("Greet.")])

    assert sent_messages(server) == [("system", "Greet.")]


class Verdict(BaseModel):
    supported: bool


def answer_with_usage(**usage: Any) -> list[str]:
    return [chunk({"role": "assistant", "content": "Aspirin is an NSAID."}), usage_chunk(**usage)]


def verdict_with_usage(**usage: Any) -> list[str]:
    return [chunk({"role": "assistant", "content": '{"supported": true}'}), usage_chunk(**usage)]


def test_openrouter_gets_the_model_that_keeps_the_cost() -> None:
    assert type(get_chat_model(openrouter_settings())) is PricedChatOpenAI


def test_a_streamed_answer_keeps_the_cost_openrouter_sends_in_its_last_chunk() -> None:
    server = LocalServer(answer_with_usage(cost=0.000123))

    message = server.model(PricedChatOpenAI).invoke("What is aspirin?")

    usage = usage_of(message)
    assert (usage.input_tokens, usage.output_tokens, usage.total_tokens) == (100, 20, 120)
    assert usage.cost_usd == 0.000123


def test_structured_output_keeps_the_cost_too() -> None:
    server = LocalServer(verdict_with_usage(cost=0.000045))
    structured = server.model(PricedChatOpenAI).with_structured_output(Verdict, include_raw=True)

    result = structured.invoke("Is it supported?")

    assert result["parsed"] == Verdict(supported=True)
    assert usage_of(result["raw"]).cost_usd == 0.000045


def test_a_response_without_a_cost_leaves_the_cost_unknown() -> None:
    server = LocalServer(answer_with_usage())

    usage = usage_of(server.model(PricedChatOpenAI).invoke("What is aspirin?"))

    assert usage.total_tokens == 120
    assert usage.cost_usd is None


def test_a_local_server_costs_nothing() -> None:
    answer = LocalServer(answer_with_usage()).model().invoke("What is aspirin?")
    verdict = (
        LocalServer(verdict_with_usage())
        .model()
        .with_structured_output(Verdict, include_raw=True)
        .invoke("Is it supported?")
    )

    assert usage_of(answer).cost_usd == 0.0
    assert usage_of(verdict["raw"]).cost_usd == 0.0


def test_structured_output_from_openrouter_keeps_its_tokens_and_cost() -> None:
    """OpenRouter repeats `"role": "assistant"` in every chunk, recorded 2026-10-19."""
    recorded = (FIXTURES / "structured_stream.sse").read_text(encoding="utf-8")
    # The server adds its own end of stream.
    server = LocalServer([recorded.removesuffix("data: [DONE]\n\n")])
    structured = server.model(PricedChatOpenAI).with_structured_output(
        RecordedVerdict, include_raw=True
    )

    result = structured.invoke("Is aspirin an NSAID?")

    assert result["parsed"] == RecordedVerdict(yes=True)
    usage = usage_of(result["raw"])
    assert (usage.input_tokens, usage.output_tokens, usage.total_tokens) == (38, 39, 77)
    assert usage.cost_usd == 2.33e-05


class RecordedVerdict(BaseModel):
    yes: bool
