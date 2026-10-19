"""Evals measure the model, not the limits on `POST /chat` (#39): a run asks hundreds of
questions a day and may run a cloud model past the daily cost limit."""

import sys

from fastapi import FastAPI

from molecula.api.dependencies import chat_limits
from molecula.guard.limits import ChatLimits, RequestLimiter


def without_chat_limits(app: FastAPI) -> None:
    unlimited = ChatLimits(RequestLimiter(sys.maxsize, sys.maxsize), None, trust_proxy=False)
    app.dependency_overrides[chat_limits] = lambda: unlimited
