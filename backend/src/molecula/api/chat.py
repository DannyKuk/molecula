import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse

from molecula.api.dependencies import (
    ChatLimitsDep,
    ChatModelDep,
    ModelChoicesDep,
    UsageLogDep,
)
from molecula.guard.limits import ChatLimited, ChatLimits
from molecula.schemas.chat import (
    ChatEvent,
    ChatModel,
    ChatRequest,
    DoneEvent,
    ErrorEvent,
    ModelChoicesResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/chat",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"text/event-stream": {}}, "description": "The answer, as it happens"},
        422: {
            "description": "The conversation is invalid, or `model` or `checker` isn't one "
            "/models lists"
        },
        429: {"description": "The client asked too many questions; see Retry-After"},
        503: {
            "description": "Chat is off (no chat model or no label index), or the day's cost "
            "limit is reached (with Retry-After)"
        },
    },
)
async def chat(
    request: ChatRequest, limits: ChatLimitsDep, choices: ModelChoicesDep, usage_log: UsageLogDep
) -> StreamingResponse:
    """Answers the conversation's last message as server-sent events: each event's name is its
    `type` and its data the event as JSON (`schemas/chat.py`). The stream ends with `done` or
    `error`; `done` says how the guard sorted the question and what it cost."""
    if request.checker is not None and not choices.offers(request.checker):
        raise HTTPException(
            status_code=422,
            detail=f"Molecula can't check messages with {request.checker} here. "
            "Pick a checker from the settings.",
        )
    picked = await choices.chat(request.model, request.checker)
    if picked is None:
        raise HTTPException(
            status_code=422,
            detail=f"Molecula has no model {request.model}. Pick one from the settings.",
        )
    model, guarded = picked
    events = usage_log.recorded(guarded.stream(request.messages), model=model.name)
    return StreamingResponse(
        server_sent(counted(events, limits)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/chat/model", responses={503: {"description": "Chat is off"}})
def model(chat_model: ChatModelDep) -> ChatModel:
    """The model that writes the answers unless a user picks another, and whether it runs
    locally."""
    return chat_model


@router.get("/models", responses={503: {"description": "Chat is off"}})
async def models(choices: ModelChoicesDep) -> ModelChoicesResponse:
    """The models a user may pick to write the answers, the default first: the configured
    model, the models the local server has and the OpenRouter models in LLM_MODELS (#37). And
    the tested models that may check the messages instead of the model that writes the answer:
    the decision model online, LOCAL_LLM_MODEL with a local server (#363)."""
    return ModelChoicesResponse(
        models=await choices.models(),
        default=choices.default.name,
        checkers=choices.checkers,
        default_checker=choices.default_checker,
    )


async def counted(events: AsyncIterator[ChatEvent], limits: ChatLimits) -> AsyncIterator[ChatEvent]:
    """The events, with the answer's cost added to the day's when `done` passes. An answer
    that fails or is stopped sends no `done`, so what its calls cost isn't added."""
    async for event in events:
        if isinstance(event, DoneEvent):
            limits.record(event.usage)
        yield event


async def turned_away(request: Request, error: Exception) -> JSONResponse:
    """A chat request a limit turned away: `detail` says when to try again, for the user, and
    `retry_after` and the Retry-After header give the seconds."""
    assert isinstance(error, ChatLimited)
    return JSONResponse(
        status_code=error.status,
        content={"detail": error.message, "retry_after": error.retry_after},
        headers={"Retry-After": str(error.retry_after)},
    )


async def server_sent(events: AsyncIterator[ChatEvent]) -> AsyncIterator[str]:
    try:
        async for event in events:
            yield frame(event)
    # Once the stream has started, the status code is sent: a failure can only be reported
    # as an event, or the client sees a broken stream.
    except Exception:
        logger.exception("The chat answer failed")
        yield frame(
            ErrorEvent(
                kind="server_error", message="Something went wrong while answering. Try again."
            )
        )


def frame(event: ChatEvent) -> str:
    return f"event: {event.type}\ndata: {event.model_dump_json()}\n\n"
