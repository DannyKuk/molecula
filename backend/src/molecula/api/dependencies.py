from typing import Annotated

from fastapi import Depends, HTTPException, Request

from molecula.agent.choices import ModelChoices
from molecula.api.login import ClerkLogin
from molecula.guard.chat import GuardedChat
from molecula.guard.limits import ChatLimited, ChatLimits
from molecula.schemas.chat import ChatModel
from molecula.schemas.retrieval import EmbeddingSetup
from molecula.services.complexes import ComplexService
from molecula.services.compounds import CompoundService
from molecula.services.knowledge_base import KnowledgeBase
from molecula.services.label_updates import LabelUpdater
from molecula.services.labels import LabelService
from molecula.services.targets import TargetService
from molecula.services.usage import UsageLog


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


def usage_log(request: Request) -> UsageLog:
    """The app's usage log, opened at startup. Tests replace it with an override."""
    return request.app.state.usage_log


UsageLogDep = Annotated[UsageLog, Depends(usage_log)]


def knowledge_base(request: Request) -> KnowledgeBase:
    """What the app's store holds, opened at startup. Tests replace it with an override."""
    return request.app.state.knowledge_base


KnowledgeBaseDep = Annotated[KnowledgeBase, Depends(knowledge_base)]


def embedding_setup(request: Request) -> EmbeddingSetup:
    """The embedding setup the settings name, read at startup. Tests replace it with an
    override."""
    return request.app.state.embedding_setup


EmbeddingSetupDep = Annotated[EmbeddingSetup, Depends(embedding_setup)]


def label_updater(request: Request) -> LabelUpdater:
    """The app's label update, built at startup. Tests replace it with an override."""
    return request.app.state.label_updater


LabelUpdaterDep = Annotated[LabelUpdater, Depends(label_updater)]


def label_update_button(updater: LabelUpdaterDep) -> LabelUpdater:
    """The label update for the dashboard's button; 404 while LABEL_UPDATE_BUTTON is off, so
    nobody starts a run with a plain request either."""
    if not updater.button:
        raise HTTPException(status_code=404, detail="Not Found")
    return updater


LabelUpdateButtonDep = Annotated[LabelUpdater, Depends(label_update_button)]


def model_choices(request: Request) -> ModelChoices[GuardedChat]:
    """The models a user may pick and the chat each answers in, the agent behind the guard,
    built at startup. Without a chat model or a label index there are none, and the chat answers
    503."""
    choices: ModelChoices[GuardedChat] | None = request.app.state.model_choices
    if choices is None:
        raise HTTPException(
            status_code=503,
            detail="Chat is off: the backend has no chat model configured or no label index "
            "built. The backend log at startup says which.",
        )
    return choices


ModelChoicesDep = Annotated[ModelChoices[GuardedChat], Depends(model_choices)]


def chat_model(request: Request) -> ChatModel:
    """The model that writes the answers; 503 when the chat is off, as for the chat itself."""
    model: ChatModel | None = request.app.state.chat_model
    if model is None:
        raise HTTPException(status_code=503, detail="Chat is off.")
    return model


ChatModelDep = Annotated[ChatModel, Depends(chat_model)]


def signed_in_user(request: Request) -> str | None:
    """The Clerk id of the user who sent the request, or None while the login is off; 401 when
    the login is on and nobody is signed in."""
    login: ClerkLogin | None = request.app.state.login
    return login.user_id(request) if login is not None else None


SignedInUserDep = Annotated[str | None, Depends(signed_in_user)]


def chat_limits(request: Request, user: SignedInUserDep, usage_log: UsageLogDep) -> ChatLimits:
    """The app's chat limits, built at startup, once they have counted this request against the
    signed-in user, or the client's address while the login is off; raises ChatLimited when they
    turn it away, and the usage log records that. Tests replace it with an override."""
    limits: ChatLimits = request.app.state.chat_limits
    client = (
        f"user:{user}" if user is not None else client_ip(request, trust_proxy=limits.trust_proxy)
    )
    try:
        limits.admit(client)
    except ChatLimited:
        usage_log.limited()
        raise
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
