from dataclasses import dataclass, field
from typing import Any

import openai
from langchain_core.language_models import BaseChatModel, LanguageModelInput
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from molecula import prompts
from molecula.config import OPENROUTER_ATTRIBUTION_HEADERS, OPENROUTER_BASE_URL, Settings

# The OpenAI client won't start without a key; Ollama and LM Studio ignore it.
LOCAL_SERVER_API_KEY = SecretStr("local")

# What the model from get_chat_model raises when a call fails: it talks to every endpoint
# through the OpenAI client.
ChatModelError = openai.APIError


class LLMConfigError(Exception):
    """The settings don't say which chat model to use, or how to reach it."""


class LocalChatOpenAI(ChatOpenAI):
    """ChatOpenAI for a local server, where gpt-oss loses the reasoning of its earlier tool calls.

    gpt-oss writes its reasoning before each tool call and expects to see it before the earlier
    calls of the same answer. LM Studio drops it from what it sends back, so after two calls
    with nothing before them the model skips reasoning and writes a garbled third call (#277).
    So the model never sees its earlier calls of an answer as calls: they and their results go
    back as one message after the question, listing each call with what it returned.
    """

    def _get_request_payload(
        self, input_: LanguageModelInput, *, stop: list[str] | None = None, **kwargs: Any
    ) -> dict[str, Any]:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        payload["messages"] = with_tool_calls_as_results(payload["messages"])
        return payload


def with_tool_calls_as_results(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """The messages with the tool calls and results after the user's latest message replaced
    by one user message that lists each call with its result."""
    last_user = max(i for i, sent in enumerate(messages) if sent["role"] == "user")
    answer = messages[last_user + 1 :]
    calls = {
        call["id"]: call["function"]
        for sent in answer
        if sent["role"] == "assistant"
        for call in sent.get("tool_calls") or []
    }
    results = [
        described_result(calls[sent["tool_call_id"]], sent["content"])
        for sent in answer
        if sent["role"] == "tool"
    ]
    if not results:
        return messages
    summary = prompts.load("agent/tool_results", results="\n\n".join(results)).strip()
    return [*messages[: last_user + 1], {"role": "user", "content": summary}]


def described_result(function: dict[str, str], result: str) -> str:
    call = f"{function['name']}({function['arguments']})"
    return prompts.load("agent/tool_result", call=call, result=result).strip()


@dataclass(frozen=True)
class Endpoint:
    base_url: str
    api_key: SecretStr
    model: str
    headers: dict[str, str] = field(default_factory=dict)
    model_class: type[ChatOpenAI] = ChatOpenAI


def get_chat_model(settings: Settings) -> BaseChatModel:
    """The chat model the settings point at: with OFFLINE=1 the local OpenAI-compatible server
    (Ollama, LM Studio) at LOCAL_LLM_BASE_URL; online, OpenRouter when OPENROUTER_API_KEY is
    set and the local server otherwise (#230).

    The model streams. Every AIMessage it returns, and the last chunk of a stream, carries the
    call's token counts in `usage_metadata`. Raises LLMConfigError when a setting is missing.
    """
    return _chat_model(settings, settings.llm_reasoning_effort)


def get_answer_model(settings: Settings) -> BaseChatModel:
    """The same model at the answering agent's own reasoning effort, ANSWER_REASONING_EFFORT."""
    return _chat_model(settings, _own_effort(settings.answer_reasoning_effort))


def get_source_check_model(settings: Settings) -> BaseChatModel:
    """The same model at the source check's own reasoning effort,
    SOURCE_CHECK_REASONING_EFFORT."""
    return _chat_model(settings, _own_effort(settings.source_check_reasoning_effort))


def _own_effort(effort: str) -> str | None:
    return None if effort == "default" else effort


def _chat_model(settings: Settings, reasoning_effort: str | None) -> BaseChatModel:
    endpoint = _resolve_endpoint(settings)
    return endpoint.model_class(
        base_url=endpoint.base_url,
        api_key=endpoint.api_key,
        model=endpoint.model,
        default_headers=endpoint.headers,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        reasoning_effort=reasoning_effort,
        streaming=True,
        # LangChain leaves streamed usage off for any base URL other than OpenAI's own.
        stream_usage=True,
    )


def chat_model_name(settings: Settings) -> str:
    """The id of the model `get_chat_model` would use, for labels; "unknown" when none is set."""
    try:
        return _resolve_endpoint(settings).model
    except LLMConfigError:
        return "unknown"


def _resolve_endpoint(settings: Settings) -> Endpoint:
    if settings.offline:
        if not settings.local_llm_base_url:
            raise LLMConfigError(
                "OFFLINE=1 needs a local chat model, and LOCAL_LLM_BASE_URL is empty. Set "
                "LOCAL_LLM_BASE_URL and LOCAL_LLM_MODEL (e.g. http://localhost:1234/v1 and "
                "openai/gpt-oss-20b for LM Studio), or set OFFLINE=0 to use OpenRouter."
            )
        return _local_endpoint(settings.local_llm_base_url, settings.local_llm_model)
    if settings.openrouter_api_key is None and settings.local_llm_base_url:
        return _local_endpoint(settings.local_llm_base_url, settings.local_llm_model)
    return _openrouter_endpoint(settings.openrouter_api_key, settings.llm_model)


def _local_endpoint(base_url: str, model: str | None) -> Endpoint:
    if not model:
        raise LLMConfigError(
            "LOCAL_LLM_BASE_URL is set but LOCAL_LLM_MODEL is empty. "
            "Set LOCAL_LLM_MODEL to a model the local server has (e.g. one from `ollama list`)."
        )
    return Endpoint(
        base_url=base_url, api_key=LOCAL_SERVER_API_KEY, model=model, model_class=LocalChatOpenAI
    )


def _openrouter_endpoint(api_key: SecretStr | None, model: str | None) -> Endpoint:
    if api_key is None:
        raise LLMConfigError(
            "No chat model is configured. Set OPENROUTER_API_KEY and LLM_MODEL to use "
            "OpenRouter, or LOCAL_LLM_BASE_URL and LOCAL_LLM_MODEL to use a local server "
            "(Ollama or LM Studio). See .env.example."
        )
    if not model:
        raise LLMConfigError(
            "OPENROUTER_API_KEY is set but LLM_MODEL is empty. "
            "Set LLM_MODEL to an OpenRouter model id (e.g. openai/gpt-4o-mini)."
        )
    return Endpoint(
        base_url=OPENROUTER_BASE_URL,
        api_key=api_key,
        model=model,
        headers=dict(OPENROUTER_ATTRIBUTION_HEADERS),
    )


def describe_provider_error(error: openai.APIError) -> str:
    """What went wrong with the chat model, for the user."""
    match error:
        case openai.APITimeoutError():
            return "The language model didn't answer in time. Try again."
        case openai.APIConnectionError():
            return "Molecula couldn't reach the language model. Check that its server is running."
        case openai.RateLimitError():
            return "The language model is busy right now (rate limit). Try again in a minute."
        case openai.AuthenticationError() | openai.PermissionDeniedError():
            return "The language model refused Molecula's API key. Check OPENROUTER_API_KEY."
        case openai.NotFoundError():
            return "The language model wasn't found. Check LLM_MODEL or LOCAL_LLM_MODEL."
        case openai.BadRequestError():
            return (
                "The language model rejected the request, for example because the "
                "conversation is longer than it can read. Start a new conversation."
            )
        case _:
            return "The language model failed. Try again."
