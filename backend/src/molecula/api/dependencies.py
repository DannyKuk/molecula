from typing import Annotated

from fastapi import Depends, HTTPException, Request

from molecula.agent.agent import ChatAgent
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


def chat_agent(request: Request) -> ChatAgent:
    """The app's chat agent, built at startup. Without a chat model or a label index there is
    none, and the chat answers 503."""
    agent: ChatAgent | None = request.app.state.chat_agent
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="Chat is off: the backend has no chat model configured or no label index "
            "built. The backend log at startup says which.",
        )
    return agent


ChatAgentDep = Annotated[ChatAgent, Depends(chat_agent)]
