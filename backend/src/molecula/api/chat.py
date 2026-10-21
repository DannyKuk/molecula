import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from molecula.api.dependencies import ChatDep, ChatLimitsDep, ChatModelDep, UsageLogDep
from molecula.guard.limits import ChatLimited, ChatLimits
from molecula.schemas.chat import ChatEvent, ChatModel, ChatRequest, DoneEvent, ErrorEvent

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/chat",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"text/event-stream": {}}, "description": "The answer, as it happens"},
        429: {"description": "The client asked too many questions; see Retry-After"},
        503: {
            "description": "Chat is off (no chat model or no label index), or the day's cost "
            "limit is reached (with Retry-After)"
        },
    },
)
async def chat(
    request: ChatRequest, limits: ChatLimitsDep, guarded: ChatDep, usage_log: UsageLogDep
) -> StreamingResponse:
    """Answers the conversation's last message as server-sent events: each event's name is its
    `type` and its data the event as JSON (`schemas/chat.py`). The stream ends with `done` or
    `error`; `done` says how the guard sorted the question and what it cost."""
    return StreamingResponse(
        server_sent(counted(usage_log.recorded(guarded.stream(request.messages)), limits)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


@router.get("/chat/model", responses={503: {"description": "Chat is off"}})
def model(chat_model: ChatModelDep) -> ChatModel:
    """The model that writes the answers and whether it runs locally, for the chat's header."""
    return chat_model


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
