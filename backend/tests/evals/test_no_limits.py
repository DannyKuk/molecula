from evals.no_limits import for_evals
from fastapi import FastAPI
from fastapi.testclient import TestClient

from molecula.api.dependencies import UsageLogDep


def test_an_eval_records_its_requests_in_memory_only() -> None:
    app = FastAPI()

    @app.get("/stored")
    def stored(usage_log: UsageLogDep) -> int:
        usage_log.limited()
        return sum(day.requests for day in usage_log.stats(days=1).days)

    for_evals(app)

    assert TestClient(app).get("/stored").json() == 1
