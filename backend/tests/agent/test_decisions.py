"""Decision-model client tests on responses recorded from LM Studio and OpenRouter
(`tests/fixtures/decisions/`, sent with `request.json`)."""

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx2
import pytest
from pydantic import SecretStr

from molecula.agent.decisions import (
    DecisionConfigError,
    DecisionModel,
    DecisionModelBadResponse,
    DecisionModelMissing,
    DecisionModelRejected,
    DecisionModelTimeout,
    DecisionModelUnreachable,
    get_decision_model,
)
from molecula.config import Settings
from molecula.schemas.decisions import (
    ChoiceQuestion,
    DecisionResponse,
    NoulCriteria,
    NoulQuestion,
    Question,
    ScoreQuestion,
    StateMessage,
)

FIXTURES = Path(__file__).parents[1] / "fixtures" / "decisions"
LM_STUDIO_URL = "http://localhost:1234/v1"
STATE = "Can I take ibuprofen with my blood pressure pills? I'm 54."
QUESTIONS: dict[str, Question] = {
    "personal": NoulQuestion(
        instructions="Does the user ask for advice about their own treatment?",
        criteria=NoulCriteria(
            true="Asks what they themselves should take or do",
            false="Asks for general information",
        ),
    ),
    "topic": ChoiceQuestion(
        instructions="What is the question about?",
        criteria={
            "interaction": "Two medicines taken together",
            "dose": "How much to take",
            "side_effect": "Unwanted effects",
            "other": "Anything else",
        },
    ),
    "urgency": ScoreQuestion(
        instructions="How urgent is the situation?",
        criteria=["Not urgent", "Soon", "Emergency"],
    ),
}
DECISION_FIELDS: dict[str, Any] = {
    "openrouter_api_key": None,
    "decision_model": None,
    "local_decision_base_url": None,
    "offline": False,
}


def fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def settings(**overrides: Any) -> Settings:
    """Settings with every decision field given, so the machine's environment can't leak in."""
    return Settings(_env_file=None, **(DECISION_FIELDS | overrides))


def lm_studio_settings(**overrides: Any) -> Settings:
    return settings(local_decision_base_url=LM_STUDIO_URL, decision_model="kev-0.8b", **overrides)


def openrouter_settings(**overrides: Any) -> Settings:
    return settings(
        openrouter_api_key=SecretStr("sk-or-test"), decision_model="jev-1.13", **overrides
    )


class Server:
    """Answers every request with one status and body, and keeps the requests."""

    def __init__(self, status: int = 200, body: Any = None, *, raw: bytes | None = None) -> None:
        self.status = status
        self.content = raw if raw is not None else json.dumps(body).encode()
        self.requests: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request)
        return httpx2.Response(self.status, content=self.content)

    @property
    def sent(self) -> dict[str, Any]:
        [request] = self.requests
        return json.loads(request.content)


def failing(error: Callable[[httpx2.Request], Exception]) -> Callable[..., httpx2.Response]:
    def handler(request: httpx2.Request) -> httpx2.Response:
        raise error(request)

    return handler


def model(settings: Settings, handler: Callable[..., httpx2.Response]) -> DecisionModel:
    return get_decision_model(settings, transport=httpx2.MockTransport(handler))


def decide(
    decision_model: DecisionModel, state: str | list[StateMessage] = STATE
) -> DecisionResponse:
    return asyncio.run(decision_model.decide(state, QUESTIONS))


def test_lm_studio_gets_the_recorded_request_without_a_key() -> None:
    server = Server(body=fixture("lmstudio/answers.json"))

    decide(model(lm_studio_settings(), server))

    [request] = server.requests
    assert str(request.url) == "http://localhost:1234/v1/systemone"
    assert "authorization" not in request.headers
    assert server.sent == fixture("request.json")


def test_kev_answers_every_question_type_with_probabilities() -> None:
    server = Server(body=fixture("lmstudio/answers.json"))

    response = decide(model(lm_studio_settings(), server))

    assert response.model == "kev-0.8b"
    assert response.noul("personal").noul == pytest.approx(0.4123, abs=1e-4)
    topic = response.choice("topic")
    assert topic.choice == "interaction"
    assert topic.probabilities.keys() == {"interaction", "dose", "side_effect", "other"}
    assert sum(topic.probabilities.values()) == pytest.approx(1.0)
    urgency = response.score("urgency")
    assert urgency.legend == {"0": "Not urgent", "1": "Soon", "2": "Emergency"}
    assert 0 <= urgency.score <= 2
    assert response.usage.input_tokens == 148


def test_an_answer_of_another_type_cannot_be_read_as_this_one() -> None:
    response = decide(model(lm_studio_settings(), Server(body=fixture("lmstudio/answers.json"))))

    with pytest.raises(TypeError, match="'topic' is a choice"):
        response.noul("topic")


def test_openrouter_gets_the_recorded_request_with_the_key_and_attribution() -> None:
    server = Server(body=fixture("openrouter/answers.json"))

    decide(model(openrouter_settings(), server))

    [request] = server.requests
    assert str(request.url) == "https://openrouter.ai/api/v1/systemone"
    assert request.headers["authorization"] == "Bearer sk-or-test"
    assert request.headers["x-openrouter-title"] == "Molecula"
    assert server.sent == fixture("request.json") | {"model": "jev-1.13"}


def test_jev_answers_under_a_dated_model_id_with_openrouter_extras() -> None:
    server = Server(body=fixture("openrouter/answers.json"))

    response = decide(model(openrouter_settings(), server))

    assert response.model == "typesafe/jev-1.13-20260917"
    assert response.noul("personal").noul == pytest.approx(0.97)
    assert response.choice("topic").probabilities["interaction"] == 1.0
    assert response.score("urgency").probabilities == {"0": 0.73, "1": 0.27, "2": 0.0}
    assert response.usage.output_tokens == 77


def test_a_conversation_goes_as_its_own_messages() -> None:
    server = Server(body=fixture("lmstudio/answers.json"))
    conversation = [
        StateMessage(role="user", content="What is ibuprofen?"),
        StateMessage(role="assistant", content="A painkiller."),
        StateMessage(role="user", content=STATE),
    ]

    decide(model(lm_studio_settings(), server), conversation)

    assert server.sent["state"] == [message.model_dump() for message in conversation]


@pytest.mark.parametrize(
    ("make_settings", "status", "body"),
    [
        (lm_studio_settings, 400, fixture("lmstudio/error_not_a_decision_model.json")),
        (openrouter_settings, 404, fixture("openrouter/error_blocked_by_guardrail.json")),
        # llama.cpp's server answers a model that isn't a decision model with 501.
        (lm_studio_settings, 501, {"error": {"code": 501, "message": "not a decision model"}}),
    ],
    ids=["lm studio: not a decision model", "openrouter: blocked by guardrail", "llama.cpp: 501"],
)
def test_a_model_the_server_cannot_serve_is_missing(
    make_settings: Callable[[], Settings], status: int, body: Any
) -> None:
    with pytest.raises(DecisionModelMissing) as error:
        decide(model(make_settings(), Server(status, body)))

    assert str(error.value) == body["error"]["message"]


def test_a_refused_request_keeps_its_status_and_message() -> None:
    server = Server(400, fixture("lmstudio/error_no_questions.json"))

    with pytest.raises(DecisionModelRejected) as error:
        decide(model(lm_studio_settings(), server))

    assert error.value.status == 400
    assert "At least one question is required" in str(error.value)


def test_an_error_without_a_json_body_keeps_the_text() -> None:
    server = Server(529, raw=b"overloaded, try again later")

    with pytest.raises(DecisionModelRejected, match="HTTP 529: overloaded"):
        decide(model(openrouter_settings(), server))


def kev_answers_with(**changes: Any) -> dict[str, Any]:
    body = fixture("lmstudio/answers.json")
    body["answers"] |= changes
    return body


@pytest.mark.parametrize(
    "body",
    [
        {k: v for k, v in fixture("lmstudio/answers.json").items() if k != "answers"},
        {**fixture("lmstudio/answers.json"), "answers": {}},
        kev_answers_with(topic={"type": "noul", "noul": 0.5}),
        kev_answers_with(urgency={"type": "box", "box": [0, 0, 1, 1]}),
        kev_answers_with(personal={"type": "noul", "noul": 1.5}),
    ],
    ids=["no answers", "an unanswered question", "wrong type", "unknown type", "not a probability"],
)
def test_a_response_without_a_valid_answer_to_every_question_is_bad(body: Any) -> None:
    with pytest.raises(DecisionModelBadResponse):
        decide(model(lm_studio_settings(), Server(body=body)))


def test_a_body_that_is_not_json_is_bad() -> None:
    with pytest.raises(DecisionModelBadResponse):
        decide(model(lm_studio_settings(), Server(raw=b"<html>proxy error</html>")))


def test_a_server_that_is_not_running_is_unreachable() -> None:
    handler = failing(lambda request: httpx2.ConnectError("refused", request=request))

    with pytest.raises(DecisionModelUnreachable, match="localhost:1234"):
        decide(model(lm_studio_settings(), handler))


def test_a_server_that_does_not_answer_in_time_times_out() -> None:
    handler = failing(lambda request: httpx2.ReadTimeout("slow", request=request))

    with pytest.raises(DecisionModelTimeout):
        decide(model(lm_studio_settings(), handler))


def test_offline_refuses_openrouter() -> None:
    with pytest.raises(DecisionConfigError, match="OFFLINE=1"):
        get_decision_model(openrouter_settings(offline=True))


def test_offline_keeps_lm_studio() -> None:
    assert get_decision_model(lm_studio_settings(offline=True)).model == "kev-0.8b"


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"local_decision_base_url": LM_STUDIO_URL}, "DECISION_MODEL is empty"),
        ({"decision_model": "jev-1.13"}, "No decision model server is configured"),
    ],
    ids=["no model", "no server"],
)
def test_missing_settings_say_what_to_set(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(DecisionConfigError, match=message):
        get_decision_model(settings(**overrides))
