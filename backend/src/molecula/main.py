import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from molecula.agent.llm import chat_model_is_local
from molecula.agent.tool_registry import McpSessions
from molecula.api import chat, drugs, health, labels, retrieval, stats
from molecula.api.dependencies import signed_in_user
from molecula.api.login import ClerkLogin
from molecula.config import Settings, get_settings
from molecula.guard.limits import ChatLimited, ChatLimits, DailyCostCap, RequestLimiter
from molecula.guard.validation import readable_validation_error
from molecula.rag.embeddings import embedding_setup
from molecula.services.knowledge_base import KnowledgeBase
from molecula.services.usage import UsageLog
from molecula.store.structures import ComplexFiles, ConformerFiles
from molecula.store.usage import UsageStore, connect_usage
from molecula.wiring import (
    log_to_console,
    open_chat,
    open_chat_model,
    open_label_index,
    open_label_updater,
    open_services,
    open_store,
    schedule_label_updates,
)

logger = logging.getLogger(__name__)


def open_chat_limits(settings: Settings) -> ChatLimits:
    """The request limit per client, and the daily cost limit unless the chat model is local,
    which costs nothing."""
    cost_cap = (
        None if chat_model_is_local(settings) else DailyCostCap(settings.daily_cost_limit_usd)
    )
    return ChatLimits(
        RequestLimiter(settings.chat_requests_per_minute, settings.chat_requests_per_day),
        cost_cap,
        trust_proxy=settings.trust_proxy,
    )


def open_login(settings: Settings) -> ClerkLogin | None:
    """The Clerk login in front of every route but /health, or None while CLERK_JWT_KEY is
    empty. The frontend's origins, CORS_ORIGINS, are the sites a token may be issued for."""
    if settings.clerk_jwt_key is None:
        logger.info("The login is off: CLERK_JWT_KEY is not set")
        return None
    logger.info("Every request needs a Clerk login from %s", ", ".join(settings.cors_origins))
    return ClerkLogin(settings.clerk_jwt_key, settings.cors_origins)


def log_api_keys(settings: Settings) -> None:
    """Which API keys the backend has, by name: a key's value never leaves its environment."""
    keys = {
        "OPENROUTER_API_KEY": settings.openrouter_api_key,
        "OPENFDA_API_KEY": settings.openfda_api_key,
    }
    for name, key in keys.items():
        logger.info("%s is %s", name, "set" if key is not None else "not set")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    log_to_console(settings.log_level)
    log_api_keys(settings)
    app.state.login = open_login(settings)
    app.state.chat_limits = open_chat_limits(settings)
    conn = open_store(settings)
    services = open_services(settings, conn)
    app.state.compound_service = services.compounds
    app.state.target_service = services.targets
    app.state.label_service = services.labels
    app.state.complex_service = services.complexes
    app.state.embedding_setup = embedding_setup(settings)
    app.state.label_retriever = None
    app.state.filter_extractor = None
    app.state.chat_agent = None
    app.state.chat = None
    app.state.chat_model = None
    app.state.model_choices = None
    index = open_label_index(settings)
    app.state.knowledge_base = KnowledgeBase(
        conn, index, ConformerFiles(settings.conformers_dir), ComplexFiles(settings.complexes_dir)
    )
    chat_model = open_chat_model(settings) if index is not None else None
    embeddings = None
    mcp_sessions = McpSessions()
    if index is not None and chat_model is not None:
        parts = await open_chat(settings, services, index, chat_model, mcp_sessions)
        embeddings = parts.embeddings
        app.state.label_retriever = parts.retriever
        app.state.filter_extractor = parts.extractor
        app.state.chat_agent = parts.agent
        app.state.chat = parts.chat
        app.state.model_choices = parts.model_choices
        app.state.chat_model = parts.model_choices.default
    usage_conn = connect_usage(settings.usage_db_path)
    app.state.usage_log = UsageLog(
        UsageStore(usage_conn), app.state.chat_model.name if app.state.chat_model else None
    )
    app.state.label_updater = open_label_updater(settings, conn, index, embeddings)
    nightly = schedule_label_updates(settings, app.state.label_updater)
    yield
    if nightly is not None:
        nightly.cancel()
    await mcp_sessions.aclose()
    usage_conn.close()
    conn.close()


app = FastAPI(title="Molecula", lifespan=lifespan)
app.add_exception_handler(RequestValidationError, readable_validation_error)
app.add_exception_handler(ChatLimited, chat.turned_away)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    # A browser hides every other response header from the page across origins.
    expose_headers=["Retry-After"],
)
app.include_router(health.router)
for router in (drugs.router, chat.router, stats.router, labels.router, retrieval.router):
    app.include_router(router, dependencies=[Depends(signed_in_user)])
