import asyncio
import logging
import secrets
import sqlite3
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel

from molecula.agent.agent import ChatAgent
from molecula.agent.decisions import DecisionConfigError, DecisionModel, get_decision_model
from molecula.agent.label_filter import DecisionFirstFilterExtractor
from molecula.agent.llm import (
    LLMConfigError,
    chat_model_is_local,
    chat_model_name,
    get_answer_model,
    get_chat_model,
    get_source_check_model,
)
from molecula.agent.tool_registry import build_tools, tools_over_mcp
from molecula.api import chat, drugs, health, labels, stats
from molecula.config import Settings, get_settings
from molecula.guard.chat import GuardedChat
from molecula.guard.limits import ChatLimited, ChatLimits, DailyCostCap, RequestLimiter
from molecula.guard.safety import ChatModelInputCheck, DecisionModelInputCheck, InputCheck
from molecula.guard.source_check import ChatModelSourceCheck
from molecula.guard.validation import readable_validation_error
from molecula.ingest.index import DrugIndexer
from molecula.ingest.update import update_store
from molecula.mcp.server import build_server
from molecula.rag.embeddings import embedding_model_id, get_embeddings
from molecula.rag.filters import FilterExtractor
from molecula.rag.retriever import LabelRetriever
from molecula.schemas.chat import ChatModel
from molecula.services.complexes import ComplexService
from molecula.services.compounds import CompoundService
from molecula.services.knowledge_base import KnowledgeBase
from molecula.services.label_updates import LabelUpdater, update_nightly
from molecula.services.labels import LabelService
from molecula.services.targets import TargetService
from molecula.services.usage import UsageLog
from molecula.store.compounds import CompoundStore
from molecula.store.db import connect
from molecula.store.index import LabelIndex
from molecula.store.keywords import KeywordIndex
from molecula.store.label_updates import LabelUpdateStore
from molecula.store.labels import LabelStore
from molecula.store.structures import ComplexFiles, ConformerFiles
from molecula.store.targets import TargetStore
from molecula.store.usage import UsageStore, connect_usage

logger = logging.getLogger(__name__)


def log_to_console(level: str) -> None:
    """Shows the app's lines from `level` up: uvicorn sets up only its own loggers, and Python
    prints nothing below WARNING without a handler."""
    app_logger = logging.getLogger("molecula")
    if not app_logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s:     %(name)s: %(message)s"))
        app_logger.addHandler(handler)
    app_logger.setLevel(level)


def open_store(settings: Settings) -> sqlite3.Connection:
    """The built store, or an empty one in memory until the first build or fetch.

    `connect` would create the file, and an empty store file would stop `ingest fetch` (#35) from
    downloading the data, so the app never creates it.
    """
    if settings.db_path.exists():
        return connect(settings.db_path)
    logger.warning("No store at %s yet; no drug is supported until it is built", settings.db_path)
    return connect(Path(":memory:"))


@dataclass(frozen=True)
class Services:
    """The services over the store, shared by the routes, the agent's tools and the MCP server."""

    compounds: CompoundService
    targets: TargetService
    labels: LabelService
    complexes: ComplexService


def open_services(settings: Settings, conn: sqlite3.Connection) -> Services:
    compounds = CompoundStore(conn)
    return Services(
        compounds=CompoundService(
            compounds,
            ConformerFiles(settings.conformers_dir),
            suggestion_cutoff=settings.name_suggestion_cutoff,
        ),
        targets=TargetService(TargetStore(conn), compounds),
        labels=LabelService(LabelStore(conn), compounds),
        complexes=ComplexService(ComplexFiles(settings.complexes_dir)),
    )


def open_label_index(settings: Settings) -> LabelIndex | None:
    """The built label index, or None until it is built. A missing index folder stays
    missing: Chroma would create it, like `connect` would create the store.

    Raises IndexModelMismatch when the index was built with another embedding model than the
    settings name, before that model is loaded.
    """
    if not settings.index_dir.exists():
        logger.warning(
            "No label index at %s yet; label search and chat are off", settings.index_dir
        )
        return None
    index = LabelIndex(settings.index_dir)
    index.check_model(embedding_model_id(settings))
    return index


def open_label_retriever(
    settings: Settings, index: LabelIndex, embeddings: Embeddings
) -> LabelRetriever:
    """The label search in RETRIEVAL_MODE. Without the keyword index, which a store fetched
    before #44 lacks, it searches by embeddings alone until `ingest fetch` builds it."""
    keywords = KeywordIndex(settings.keyword_index_path)
    mode = settings.retrieval_mode
    if mode != "dense" and not keywords.exists():
        logger.warning(
            "No keyword index at %s; RETRIEVAL_MODE=%s searches by embeddings only. "
            "`python -m molecula.ingest fetch` builds it from the label index",
            settings.keyword_index_path,
            mode,
        )
        mode = "dense"
    return LabelRetriever(
        index,
        embeddings,
        top_k=settings.retrieval_top_k,
        min_score=settings.retrieval_min_score,
        section_group_boost=settings.retrieval_section_group_boost,
        mode=mode,
        keywords=keywords,
    )


def open_label_updater(
    settings: Settings,
    conn: sqlite3.Connection,
    index: LabelIndex | None,
    embeddings: Embeddings | None,
) -> LabelUpdater:
    """The label update over the app's own index and embedding model: Chroma lets only one
    process write to the index, and a second copy of the model would double the memory."""
    runs = LabelUpdateStore(conn)
    button = settings.label_update_button
    if settings.offline:
        reason = "OFFLINE=1: a label update needs openFDA."
        return LabelUpdater(runs, None, button=button, off_reason=reason)
    if index is None or not settings.db_path.exists():
        reason = "There is no built store and label index to update yet."
        return LabelUpdater(runs, None, button=button, off_reason=reason)
    return LabelUpdater(
        runs,
        lambda: update_store(settings, DrugIndexer(settings, embeddings=embeddings, index=index)),
        button=button,
    )


def schedule_label_updates(settings: Settings, updater: LabelUpdater) -> asyncio.Task[None] | None:
    """The nightly label update, unless LABEL_UPDATE_SCHEDULE=0 or the backend can't update."""
    if not settings.label_update_schedule:
        return None
    if not updater.can_run:
        logger.info("No nightly label update: %s", updater.off_reason)
        return None
    logger.info("The labels are updated every day at %02d:00 UTC", settings.label_update_hour)
    return asyncio.create_task(update_nightly(updater.start, settings.label_update_hour))


def open_chat_model(settings: Settings) -> BaseChatModel | None:
    """The chat model, or None while none is configured: the chat and the label search are then
    off, and the data routes still work."""
    try:
        return get_chat_model(settings)
    except LLMConfigError as error:
        logger.warning("Label search and chat are off: %s", error)
        return None


def open_input_check(settings: Settings, chat_model: BaseChatModel) -> InputCheck:
    """The decision model sorts messages online (Jev on OpenRouter by default), the chat model
    offline or when no decision model is configured (#226)."""
    decision_model = online_decision_model(settings)
    if decision_model is None:
        return ChatModelInputCheck(chat_model)
    return DecisionModelInputCheck(decision_model)


def open_filter_extractor(
    settings: Settings,
    chat_model: BaseChatModel,
    compounds: CompoundService,
    labels: LabelService,
) -> FilterExtractor:
    """The decision model extracts the label filter online, the chat model when it fails, and
    the chat model alone offline or when no decision model is configured (#290)."""
    decision_model = online_decision_model(settings)
    if decision_model is None:
        return FilterExtractor(chat_model, compounds, labels)
    return DecisionFirstFilterExtractor(chat_model, decision_model, compounds, labels)


def online_decision_model(settings: Settings) -> DecisionModel | None:
    if settings.offline:
        return None
    try:
        return get_decision_model(settings)
    except DecisionConfigError as error:
        logger.warning("The chat model sorts messages and extracts label filters: %s", error)
        return None


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
    app.state.chat_limits = open_chat_limits(settings)
    conn = open_store(settings)
    services = open_services(settings, conn)
    app.state.compound_service = services.compounds
    app.state.target_service = services.targets
    app.state.label_service = services.labels
    app.state.complex_service = services.complexes
    app.state.label_retriever = None
    app.state.filter_extractor = None
    app.state.chat_agent = None
    app.state.chat = None
    app.state.chat_model = None
    index = open_label_index(settings)
    app.state.knowledge_base = KnowledgeBase(
        conn, index, ConformerFiles(settings.conformers_dir), ComplexFiles(settings.complexes_dir)
    )
    chat_model = open_chat_model(settings) if index is not None else None
    embeddings = None
    mcp_session = AsyncExitStack()
    if index is not None and chat_model is not None:
        embeddings = get_embeddings(settings)
        app.state.label_retriever = open_label_retriever(settings, index, embeddings)
        app.state.filter_extractor = open_filter_extractor(
            settings, chat_model, services.compounds, services.labels
        )
        tools = build_tools(
            services.compounds,
            services.targets,
            services.complexes,
            app.state.filter_extractor,
            app.state.label_retriever,
        )
        if settings.agent_tools == "mcp":
            tools = await mcp_session.enter_async_context(
                tools_over_mcp(build_server(tools), tools)
            )
        app.state.chat_agent = ChatAgent(
            get_answer_model(settings),
            tools,
            canary=secrets.token_hex(16),
            max_steps=settings.chat_max_steps,
            timeout_seconds=settings.chat_timeout_seconds,
        )
        app.state.chat = GuardedChat(
            open_input_check(settings, chat_model),
            app.state.chat_agent,
            ChatModelSourceCheck(get_source_check_model(settings)),
            timeout_seconds=settings.llm_timeout_seconds,
        )
        app.state.chat_model = ChatModel(
            name=chat_model_name(settings), local=chat_model_is_local(settings)
        )
    usage_conn = connect_usage(settings.usage_db_path)
    app.state.usage_log = UsageLog(
        UsageStore(usage_conn), app.state.chat_model.name if app.state.chat_model else None
    )
    app.state.label_updater = open_label_updater(settings, conn, index, embeddings)
    nightly = schedule_label_updates(settings, app.state.label_updater)
    yield
    if nightly is not None:
        nightly.cancel()
    await mcp_session.aclose()
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
app.include_router(drugs.router)
app.include_router(chat.router)
app.include_router(stats.router)
app.include_router(labels.router)
