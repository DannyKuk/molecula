from evals.no_limits import for_evals
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from clerk_tokens import clerk_login
from molecula.api.dependencies import UsageLogDep, signed_in_user


def test_an_eval_records_its_requests_in_memory_only() -> None:
    app = FastAPI()

    @app.get("/stored")
    def stored(usage_log: UsageLogDep) -> int:
        usage_log.limited()
        return sum(day.requests for day in usage_log.stats(days=1).days)

    for_evals(app)

    assert TestClient(app).get("/stored").json() == 1


def test_an_eval_asks_without_a_login_even_when_the_app_has_one() -> None:
    app = FastAPI()
    app.state.login = clerk_login()

    @app.get("/asked", dependencies=[Depends(signed_in_user)])
    def asked() -> str:
        return "answered"

    for_evals(app)

    assert TestClient(app).get("/asked").status_code == 200
