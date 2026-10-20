from collections.abc import Callable, Iterator

import pytest
from fastapi.testclient import TestClient

from fake_llm import CANARY, ScriptedChatModel, answer_message
from guard_fakes import FakeCheck, FakeSourceCheck
from molecula.agent.agent import ChatAgent
from molecula.agent.tool_registry import build_tools
from molecula.api.dependencies import chat
from molecula.config import Settings
from molecula.guard.chat import GuardedChat
from molecula.guard.limits import ChatLimits, DailyCostCap, RequestLimiter
from molecula.main import app, open_chat_limits
from tool_fakes import (
    FakeComplexService,
    FakeCompoundService,
    FakeFilterExtractor,
    FakeLabelRetriever,
    FakeTargetService,
)

QUESTION = {"messages": [{"role": "user", "content": "What does imatinib target?"}]}
CLIENT = ("203.0.113.5", 50000)
PROXY = ("10.0.0.2", 50000)


def guarded(answers: int) -> GuardedChat:
    tools = build_tools(
        FakeCompoundService(),
        FakeTargetService(),
        FakeComplexService(),
        FakeFilterExtractor(),
        FakeLabelRetriever(),
    )
    model = ScriptedChatModel(script=[answer_message("Imatinib blocks ABL1.")] * answers)
    agent = ChatAgent(model, tools, canary=CANARY, max_steps=5, timeout_seconds=10)
    return GuardedChat(FakeCheck(), agent, FakeSourceCheck(), timeout_seconds=5)


@pytest.fixture
def limited() -> Iterator[Callable[..., ChatLimits]]:
    """Puts limits on the app's chat, in front of a scripted agent."""

    def limit(
        per_minute: int = 2, cost_cap: DailyCostCap | None = None, *, trust_proxy: bool = False
    ) -> ChatLimits:
        limits = ChatLimits(RequestLimiter(per_minute, 100), cost_cap, trust_proxy=trust_proxy)
        app.state.chat_limits = limits
        return limits

    app.dependency_overrides[chat] = lambda: guarded(answers=10)
    yield limit
    app.dependency_overrides.clear()
    del app.state.chat_limits


def ask(client: TestClient, **headers: str) -> int:
    return client.post("/chat", json=QUESTION, headers=headers).status_code


def test_the_request_over_the_limit_gets_429_with_retry_after(
    limited: Callable[..., ChatLimits],
) -> None:
    limited(per_minute=2)
    client = TestClient(app, client=CLIENT)
    assert [ask(client), ask(client)] == [200, 200]

    response = client.post("/chat", json=QUESTION)

    assert response.status_code == 429
    assert response.headers["retry-after"] == "60"
    assert response.json()["retry_after"] == 60
    assert "Try again in 1 minute" in response.json()["detail"]


def test_another_client_is_still_answered(limited: Callable[..., ChatLimits]) -> None:
    limited(per_minute=1)
    ask(TestClient(app, client=CLIENT))

    assert ask(TestClient(app, client=("198.51.100.7", 50000))) == 200


def test_x_forwarded_for_is_ignored_without_trust_proxy(
    limited: Callable[..., ChatLimits],
) -> None:
    limited(per_minute=1)
    client = TestClient(app, client=CLIENT)
    ask(client, **{"X-Forwarded-For": "192.0.2.1"})

    assert ask(client, **{"X-Forwarded-For": "192.0.2.2"}) == 429


def test_behind_a_trusted_proxy_the_address_it_added_counts(
    limited: Callable[..., ChatLimits],
) -> None:
    limited(per_minute=1, trust_proxy=True)
    proxy = TestClient(app, client=PROXY)
    ask(proxy, **{"X-Forwarded-For": "203.0.113.5"})

    # A client can write its own X-Forwarded-For; the proxy adds the real address at the end.
    assert ask(proxy, **{"X-Forwarded-For": "192.0.2.9, 203.0.113.5"}) == 429
    assert ask(proxy, **{"X-Forwarded-For": "198.51.100.7"}) == 200


def test_answers_add_their_cost_until_the_cap_turns_requests_away(
    limited: Callable[..., ChatLimits],
) -> None:
    # The scripted check, answer and source check cost $0.0007 per answer (guard_fakes.py).
    limits = limited(per_minute=10, cost_cap=DailyCostCap(0.001))
    client = TestClient(app, client=CLIENT)
    assert [ask(client), ask(client)] == [200, 200]

    response = client.post("/chat", json=QUESTION)

    assert limits.cost_cap is not None
    assert limits.cost_cap.spent_usd == pytest.approx(0.0014)
    assert response.status_code == 503
    assert int(response.headers["retry-after"]) > 0
    assert "today's budget" in response.json()["detail"]


def test_a_local_chat_model_has_no_cost_cap(make_settings: Callable[..., Settings]) -> None:
    local = make_settings(local_llm_base_url="http://localhost:1234/v1", local_llm_model="m")
    cloud = make_settings(offline=False, openrouter_api_key="sk-or-test", llm_model="m")

    assert open_chat_limits(local).cost_cap is None
    assert open_chat_limits(cloud).cost_cap is not None
