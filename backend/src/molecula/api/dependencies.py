from typing import Annotated

from fastapi import Depends, HTTPException, Request

from molecula.guard.chat import GuardedChat
from molecula.guard.limits import ChatLimits
from molecula.schemas.chat import ChatModel
from molecula.services.complexes import ComplexService
from molecula.services.compounds import CompoundService
from molecula.services.labels import LabelService
from molecula.services.targets import TargetService


def compound_service(request: Request) -> CompoundService:
    """The app's one compound service, built at startup. Tests replace it with an override."""
    return request.app.state.compound_service


CompoundServiceDep = Annotated[CompoundService, Depends(compound_service)]


def target_service(request: Request) -> TargetService:
    """The app's one target service, built at startup. Tests replace it with an override."""
    return request.app.state.target_service


TargetServiceDep = Annotated[TargetService, Depends(target_service)]


def label_service(request: Request) -> LabelService:
    """The app's one label service, built at startup. Tests replace it with an override."""
    return request.app.state.label_service


LabelServiceDep = Annotated[LabelService, Depends(label_service)]


def complex_service(request: Request) -> ComplexService:
    """The app's one complex service, built at startup. Tests replace it with an override."""
    return request.app.state.complex_service


ComplexServiceDep = Annotated[ComplexService, Depends(complex_service)]


def chat(request: Request) -> GuardedChat:
    """The app's chat, the agent behind the guard, built at startup. Without a chat model or a
    label index there is none, and the chat answers 503."""
    guarded: GuardedChat | None = request.app.state.chat
    if guarded is None:
        raise HTTPException(
            status_code=503,
            detail="Chat is off: the backend has no chat model configured or no label index "
            "built. The backend log at startup says which.",
        )
    return guarded


ChatDep = Annotated[GuardedChat, Depends(chat)]


def chat_model(request: Request) -> ChatModel:
    """The model that writes the answers; 503 when the chat is off, as for the chat itself."""
    model: ChatModel | None = request.app.state.chat_model
    if model is None:
        raise HTTPException(status_code=503, detail="Chat is off.")
    return model


ChatModelDep = Annotated[ChatModel, Depends(chat_model)]


def chat_limits(request: Request) -> ChatLimits:
    """The app's chat limits, built at startup, once they have counted this request; raises
    ChatLimited when they turn it away. Tests replace it with an override."""
    limits: ChatLimits = request.app.state.chat_limits
    limits.admit(client_ip(request, trust_proxy=limits.trust_proxy))
    return limits


ChatLimitsDep = Annotated[ChatLimits, Depends(chat_limits)]


def client_ip(request: Request, *, trust_proxy: bool) -> str:
    """The address the request came from. Behind a proxy (`trust_proxy`) that is the last
    X-Forwarded-For entry, the one the proxy added; the entries before it are whatever the
    client sent, so they are never read."""
    forwarded = request.headers.get("x-forwarded-for", "")
    if trust_proxy and forwarded.strip():
        return forwarded.split(",")[-1].strip()
    return request.client.host if request.client else "unknown"
