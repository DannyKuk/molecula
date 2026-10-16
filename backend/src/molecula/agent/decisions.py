from collections.abc import Mapping
from typing import Any

import httpx2
from pydantic import SecretStr, ValidationError

from molecula.agent.llm import Endpoint
from molecula.config import OPENROUTER_ATTRIBUTION_HEADERS, OPENROUTER_BASE_URL, Settings
from molecula.schemas.decisions import (
    DecisionRequest,
    DecisionResponse,
    Question,
    StateMessage,
)

SYSTEMONE_PATH = "/systemone"
# LM Studio's codes, sent with HTTP 400, for a model id it can't serve as a decision model:
# not downloaded, not a decision model, or none given while nothing is loaded.
LM_STUDIO_MISSING_MODEL_CODES = frozenset({"invalidModelIdentifier", "noModelsLoaded"})


class DecisionConfigError(Exception):
    """The settings don't say which decision model to use, or how to reach it."""


class DecisionModelError(Exception):
    """Base for every error a decision-model call raises."""


class DecisionModelUnreachable(DecisionModelError):
    """The server didn't accept the connection or broke it off."""


class DecisionModelTimeout(DecisionModelError):
    """The server didn't answer within DECISION_TIMEOUT_SECONDS."""


class DecisionModelMissing(DecisionModelError):
    """The server can't serve the model as a decision model: LM Studio hasn't downloaded it or
    it isn't one, or OpenRouter has no endpoint for it (also when a workspace guardrail blocks
    it)."""


class DecisionModelRejected(DecisionModelError):
    """The server refused the request: bad request, API key, credits, rate limit, overload."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(f"HTTP {status}: {message}")
        self.status = status


class DecisionModelBadResponse(DecisionModelError):
    """The server answered 200, but not with an answer of the asked type for every question."""


class DecisionModel:
    """Asks a decision model typed questions about a state over `/v1/systemone`. Each question
    gets an answer with probabilities in one call; nothing is retried, so a check built on it
    fails fast."""

    def __init__(
        self,
        endpoint: Endpoint,
        *,
        timeout_seconds: float,
        transport: httpx2.AsyncBaseTransport | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._timeout = httpx2.Timeout(timeout_seconds)
        self._transport = transport

    @property
    def model(self) -> str:
        return self._endpoint.model

    async def decide(
        self, state: str | list[StateMessage], questions: Mapping[str, Question]
    ) -> DecisionResponse:
        """The answers keyed by the question ids. A message list as the state keeps a
        conversation in its own messages. Raises a DecisionModelError when there's no answer."""
        request = DecisionRequest(
            model=self._endpoint.model, state=state, questions=dict(questions)
        )
        response = await self._post(request.model_dump(mode="json", exclude_none=True))
        return checked(request, parsed(response))

    async def _post(self, payload: dict[str, Any]) -> httpx2.Response:
        async with httpx2.AsyncClient(transport=self._transport, timeout=self._timeout) as client:
            try:
                return await client.post(
                    self._endpoint.base_url + SYSTEMONE_PATH,
                    json=payload,
                    headers=auth_headers(self._endpoint),
                )
            except httpx2.TimeoutException as error:
                raise DecisionModelTimeout(f"{self._endpoint.base_url}: {error!r}") from error
            except httpx2.TransportError as error:
                raise DecisionModelUnreachable(f"{self._endpoint.base_url}: {error!r}") from error


def get_decision_model(
    settings: Settings, *, transport: httpx2.AsyncBaseTransport | None = None
) -> DecisionModel:
    """The decision model the settings point at: LM Studio when LOCAL_DECISION_BASE_URL is set,
    otherwise Jev on OpenRouter, which OFFLINE=1 refuses. Raises DecisionConfigError when a
    setting is missing."""
    if not settings.decision_model:
        raise DecisionConfigError(
            "DECISION_MODEL is empty. Set it to the decision model loaded in LM Studio "
            "(e.g. kev-0.8b) with LOCAL_DECISION_BASE_URL, or to a Jev id on OpenRouter "
            "(e.g. jev-1.13). See .env.example."
        )
    endpoint = _resolve_endpoint(settings, settings.decision_model)
    return DecisionModel(
        endpoint, timeout_seconds=settings.decision_timeout_seconds, transport=transport
    )


def _resolve_endpoint(settings: Settings, model: str) -> Endpoint:
    if settings.local_decision_base_url:
        # LM Studio needs no key; the empty one keeps the Authorization header off.
        return Endpoint(
            base_url=settings.local_decision_base_url, api_key=SecretStr(""), model=model
        )
    if settings.offline:
        raise DecisionConfigError(
            "OFFLINE=1 and no LOCAL_DECISION_BASE_URL: the decision model would be Jev on "
            "OpenRouter, an external call. Set LOCAL_DECISION_BASE_URL to LM Studio "
            "(e.g. http://localhost:1234/v1)."
        )
    if settings.openrouter_api_key is None:
        raise DecisionConfigError(
            "No decision model server is configured. Set OPENROUTER_API_KEY to use Jev on "
            "OpenRouter, or LOCAL_DECISION_BASE_URL to use LM Studio. See .env.example."
        )
    return Endpoint(
        base_url=OPENROUTER_BASE_URL,
        api_key=settings.openrouter_api_key,
        model=model,
        headers=dict(OPENROUTER_ATTRIBUTION_HEADERS),
    )


def auth_headers(endpoint: Endpoint) -> dict[str, str]:
    key = endpoint.api_key.get_secret_value()
    return endpoint.headers | ({"Authorization": f"Bearer {key}"} if key else {})


def parsed(response: httpx2.Response) -> DecisionResponse:
    if response.status_code != 200:
        raise status_error(response)
    try:
        return DecisionResponse.model_validate_json(response.content)
    except ValidationError as error:
        raise DecisionModelBadResponse(str(error)) from error


def status_error(response: httpx2.Response) -> DecisionModelError:
    """The typed error for a failed call. LM Studio says a model is missing with HTTP 400 and
    a code, llama.cpp with 501, OpenRouter with 404."""
    code, message = error_body(response)
    if response.status_code in (404, 501) or code in LM_STUDIO_MISSING_MODEL_CODES:
        return DecisionModelMissing(message)
    return DecisionModelRejected(response.status_code, message)


def error_body(response: httpx2.Response) -> tuple[str | None, str]:
    """The error's code and message from the OpenAI-style `{"error": {...}}` body that
    OpenRouter, LM Studio and llama.cpp send, or the start of the body when it isn't one."""
    try:
        error = response.json()["error"]
        code = error.get("code")
        return (None if code is None else str(code)), str(error["message"])
    except ValueError, KeyError, TypeError, AttributeError:
        return None, response.text[:300]


def checked(request: DecisionRequest, response: DecisionResponse) -> DecisionResponse:
    """The response, once every question has an answer of its own type."""
    for key, question in request.questions.items():
        answer = response.answers.get(key)
        if answer is None:
            raise DecisionModelBadResponse(f"no answer for question {key!r}")
        if answer.type != question.type:
            raise DecisionModelBadResponse(
                f"question {key!r} is a {question.type}, the answer a {answer.type}"
            )
    return response
