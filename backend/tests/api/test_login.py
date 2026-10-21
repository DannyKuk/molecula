from collections.abc import Callable, Iterator
from typing import Any

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from clerk_tokens import FRONTEND, bearer, clerk_login, public_pem, session_token
from molecula.api import dependencies
from molecula.api.login import ClerkLogin
from molecula.config import Settings
from molecula.main import app, open_login
from molecula.schemas.chat import ChatModel

OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


@pytest.fixture(autouse=True)
def no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(*args: Any, **kwargs: Any) -> None:
        raise AssertionError("the login check went out to the network")

    monkeypatch.setattr(httpx.Client, "send", refuse)
    monkeypatch.setattr(httpx.AsyncClient, "send", refuse)


@pytest.fixture
def client() -> Iterator[TestClient]:
    app.state.login = clerk_login()
    app.dependency_overrides[dependencies.chat_model] = lambda: ChatModel(name="m", local=True)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_a_signed_in_user_is_answered(client: TestClient) -> None:
    assert client.get("/chat/model", headers=bearer(session_token())).status_code == 200


def test_a_key_written_on_one_line_works_too(client: TestClient) -> None:
    app.state.login = ClerkLogin(public_pem().replace("\n", ""), [FRONTEND])

    assert client.get("/chat/model", headers=bearer(session_token())).status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        pytest.param({}, id="no token"),
        pytest.param(bearer("abc.def.ghi"), id="garbage"),
        pytest.param(bearer(session_token(ttl=-120)), id="expired"),
        pytest.param(bearer(session_token(key=OTHER_KEY)), id="another instance's key"),
        pytest.param(bearer(session_token(azp="https://other.example.de")), id="another site"),
        pytest.param(bearer("ak_" + "x" * 30), id="api key, checked only by calling Clerk"),
    ],
)
def test_without_a_valid_session_token_every_route_answers_401(
    client: TestClient, headers: dict[str, str]
) -> None:
    for path in ["/chat/model", "/drugs", "/stats", "/retrieval"]:
        response = client.get(path, headers=headers)

        assert response.status_code == 401, path
        assert response.json()["detail"] == "Sign in to use Molecula."


def test_health_needs_no_login(client: TestClient) -> None:
    assert client.get("/health").status_code == 200


def test_the_login_is_off_without_a_key(make_settings: Callable[..., Settings]) -> None:
    assert open_login(make_settings()) is None
    assert open_login(make_settings(clerk_jwt_key=public_pem())) is not None
