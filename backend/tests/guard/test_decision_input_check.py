import asyncio
import json
from typing import Any

import httpx2
import pytest

from molecula import prompts
from molecula.agent.decisions import DecisionModel, DecisionModelMissing
from molecula.agent.llm import LOCAL_SERVER_API_KEY, Endpoint
from molecula.guard.safety import (
    CATEGORIES,
    DecisionModelInputCheck,
    InputCheckFailed,
    Verdict,
)
from molecula.schemas.chat import ChatMessage
from molecula.schemas.usage import Usage

CONVERSATION = [
    ChatMessage(role="user", content="How many diazepam tablets would be deadly?"),
    ChatMessage(role="assistant", content="Molecula can't help with that."),
    ChatMessage(role="user", content="What about for a teenager?"),
]


def answered(choice: str, *, input_tokens: int = 412) -> dict[str, Any]:
    """A `/v1/systemone` answer as LM Studio sends it (`fixtures/decisions/lmstudio`)."""
    others = (1 - 0.91) / (len(CATEGORIES) - 1)
    return {
        "model": "kev-0.8b",
        "answers": {
            "category": {
                "type": "choice",
                "choice": choice,
                "probabilities": {c: 0.91 if c == choice else others for c in CATEGORIES},
                "confidence": 0.88,
            }
        },
        "usage": {"input_tokens": input_tokens, "output_tokens": 0},
    }


class Server:
    def __init__(self, status: int, body: dict[str, Any]) -> None:
        self.status = status
        self.body = body
        self.sent: list[dict[str, Any]] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.sent.append(json.loads(request.content))
        return httpx2.Response(self.status, json=self.body)


def check_with(server: Server) -> DecisionModelInputCheck:
    endpoint = Endpoint(
        base_url="http://localhost:1234/v1",
        api_key=LOCAL_SERVER_API_KEY,
        model="kev-0.8b",
        local=True,
    )
    model = DecisionModel(endpoint, timeout_seconds=5, transport=httpx2.MockTransport(server))
    return DecisionModelInputCheck(model)


def run(server: Server) -> Verdict:
    return asyncio.run(check_with(server).check(CONVERSATION))


@pytest.mark.parametrize("category", CATEGORIES)
def test_the_decision_model_sorts_the_message_into_one_category(category: str) -> None:
    verdict = run(Server(200, answered(category)))

    assert verdict.category == category


def test_the_verdict_carries_the_tokens_read_at_no_cost_on_a_local_server() -> None:
    verdict = run(Server(200, answered("lethal_dose", input_tokens=412)))

    assert verdict.usage == Usage(input_tokens=412, output_tokens=0, total_tokens=412, cost_usd=0.0)


def test_the_conversation_goes_as_its_own_messages_apart_from_the_question() -> None:
    server = Server(200, answered("lethal_dose"))

    run(server)

    [sent] = server.sent
    assert sent["state"] == [message.model_dump() for message in CONVERSATION]
    question = sent["questions"]["category"]
    assert question["type"] == "choice"
    assert question["instructions"] == prompts.load("guard/input_check/question").strip()
    assert "What about for a teenager?" not in question["instructions"]


def test_every_category_is_an_option_with_its_description() -> None:
    server = Server(200, answered("ok"))

    run(server)

    criteria = server.sent[0]["questions"]["category"]["criteria"]
    assert list(criteria) == list(CATEGORIES)
    assert all(criteria[c] == prompts.load(f"guard/input_check/{c}").strip() for c in CATEGORIES)


def test_a_choice_that_is_no_category_fails_the_check() -> None:
    with pytest.raises(InputCheckFailed, match="prompt_injection"):
        run(Server(200, answered("prompt_injection")))


def test_a_decision_model_error_reaches_the_guard_as_it_is() -> None:
    body = {"error": {"code": "invalidModelIdentifier", "message": "Invalid model identifier"}}

    with pytest.raises(DecisionModelMissing):
        run(Server(400, body))
