import logging
from collections.abc import AsyncIterator

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from molecula.api.dependencies import ChatAgentDep
from molecula.schemas.chat import ChatEvent, ChatRequest, ErrorEvent

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/chat",
    response_class=StreamingResponse,
    responses={
        200: {"content": {"text/event-stream": {}}, "description": "The answer, as it happens"},
        503: {"description": "Chat is off: no chat model or no label index"},
    },
)
async def chat(request: ChatRequest, agent: ChatAgentDep) -> StreamingResponse:
    """Answers the conversation's last message as server-sent events: each event's name is its
    `type` and its data the event as JSON (`schemas/chat.py`). The stream ends with `done` or
    `error`."""
    return StreamingResponse(
        server_sent(agent.stream(request.messages)),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )


async def server_sent(events: AsyncIterator[ChatEvent]) -> AsyncIterator[str]:
    try:
        async for event in events:
            yield frame(event)
    # Once the stream has started, the status code is sent: a failure can only be reported
    # as an event, or the client sees a broken stream.
    except Exception:
        logger.exception("The chat answer failed")
        yield frame(ErrorEvent(message="Something went wrong while answering. Try again."))


def frame(event: ChatEvent) -> str:
    return f"event: {event.type}\ndata: {event.model_dump_json()}\n\n"
