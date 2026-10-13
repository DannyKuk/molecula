from dataclasses import dataclass, field

import openai
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from molecula.config import OPENROUTER_ATTRIBUTION_HEADERS, OPENROUTER_BASE_URL, Settings

# The OpenAI client won't start without a key; Ollama and LM Studio ignore it.
LOCAL_SERVER_API_KEY = SecretStr("local")

# What the model from get_chat_model raises when a call fails: it talks to every endpoint
# through the OpenAI client.
ChatModelError = openai.APIError


class LLMConfigError(Exception):
    """The settings don't say which chat model to use, or how to reach it."""


@dataclass(frozen=True)
class Endpoint:
    base_url: str
    api_key: SecretStr
    model: str
    headers: dict[str, str] = field(default_factory=dict)


def get_chat_model(settings: Settings) -> BaseChatModel:
    """The chat model the settings point at: a local OpenAI-compatible server (Ollama,
    LM Studio) when LOCAL_LLM_BASE_URL is set, otherwise OpenRouter.

    The model streams. Every AIMessage it returns, and the last chunk of a stream, carries the
    call's token counts in `usage_metadata`. Raises LLMConfigError when a setting is missing.
    """
    endpoint = _resolve_endpoint(settings)
    return ChatOpenAI(
        base_url=endpoint.base_url,
        api_key=endpoint.api_key,
        model=endpoint.model,
        default_headers=endpoint.headers,
        temperature=settings.llm_temperature,
        timeout=settings.llm_timeout_seconds,
        max_retries=settings.llm_max_retries,
        streaming=True,
        # LangChain leaves streamed usage off for any base URL other than OpenAI's own.
        stream_usage=True,
    )


def _resolve_endpoint(settings: Settings) -> Endpoint:
    if settings.local_llm_base_url:
        return _local_endpoint(settings.local_llm_base_url, settings.local_llm_model)
    return _openrouter_endpoint(settings.openrouter_api_key, settings.llm_model)


def _local_endpoint(base_url: str, model: str | None) -> Endpoint:
    if not model:
        raise LLMConfigError(
            "LOCAL_LLM_BASE_URL is set but LOCAL_LLM_MODEL is empty. "
            "Set LOCAL_LLM_MODEL to a model the local server has (e.g. one from `ollama list`)."
        )
    return Endpoint(base_url=base_url, api_key=LOCAL_SERVER_API_KEY, model=model)


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
