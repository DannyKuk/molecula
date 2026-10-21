"""Evals measure the model, not the limits on `POST /chat` (#39): a run asks hundreds of
questions a day and may run a cloud model past the daily cost limit. Its questions aren't the
app's use either, so they stay out of the usage log the dashboard shows (#334)."""

import sys
from pathlib import Path

from fastapi import FastAPI

from molecula.api.dependencies import chat_limits, usage_log
from molecula.guard.limits import ChatLimits, RequestLimiter
from molecula.services.usage import UsageLog
from molecula.store.usage import UsageStore, connect_usage


def for_evals(app: FastAPI) -> None:
    """Turns the chat's limits off and records its requests in a usage log in memory."""
    unlimited = ChatLimits(RequestLimiter(sys.maxsize, sys.maxsize), None, trust_proxy=False)
    unrecorded = UsageLog(UsageStore(connect_usage(Path(":memory:"))), None)
    app.dependency_overrides[chat_limits] = lambda: unlimited
    app.dependency_overrides[usage_log] = lambda: unrecorded
