"""Builds the app's parts from the settings: the store and its services, the label search, the
models, the agent's tools and the guarded chat. The web app (`main.py`) and the MCP server
(`mcp/__main__.py`) both start from here."""

import asyncio
import logging
import secrets
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from functools import partial
from pathlib import Path

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.tools import BaseTool

from molecula.agent.agent import ChatAgent
from molecula.agent.choices import ModelChoices
from molecula.agent.decisions import DecisionConfigError, DecisionModel, get_decision_model
from molecula.agent.label_filter import DecisionFirstFilterExtractor
from molecula.agent.llm import (
    LLMConfigError,
    chat_model_is_local,
    chat_model_name,
    cloud_model_choices,
    get_answer_model,
    get_chat_model,
    get_source_check_model,
    local_model_names,
)
from molecula.agent.tool_registry import McpSessions, build_tools
from molecula.config import Settings
from molecula.guard.chat import GuardedChat
from molecula.guard.safety import ChatModelInputCheck, DecisionModelInputCheck, InputCheck
from molecula.guard.source_check import ChatModelSourceCheck
from molecula.ingest.index import DrugIndexer
from molecula.ingest.update import update_store
from molecula.mcp.server import build_server
from molecula.rag.embeddings import embedding_model_id, get_embeddings
from molecula.rag.filters import FilterExtractor
from molecula.rag.retriever import LabelRetriever
from molecula.schemas.chat import ChatModel, Checker, CheckerId
from molecula.services.complexes import ComplexService
from molecula.services.compounds import CompoundService
from molecula.services.label_updates import LabelUpdater, update_nightly
from molecula.services.labels import LabelService
from molecula.services.targets import TargetService
from molecula.store.compounds import CompoundStore
from molecula.store.db import StoreConnection, connect
from molecula.store.index import LabelIndex
from molecula.store.keywords import KeywordIndex
from molecula.store.label_updates import LabelUpdateStore
from molecula.store.labels import LabelStore
from molecula.store.structures import ComplexFiles, ConformerFiles
from molecula.store.targets import TargetStore

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


def open_store(settings: Settings) -> StoreConnection:
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


def open_services(settings: Settings, conn: StoreConnection) -> Services:
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
        section_group_boost=settings.section_group_boost,
        mode=mode,
        keywords=keywords,
    )


def open_label_updater(
    settings: Settings,
    conn: StoreConnection,
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
        chat_model = get_chat_model(settings)
    except LLMConfigError as error:
        logger.warning("Label search and chat are off: %s", error)
        return None
    # Says at the start which server the answers need, e.g. LM Studio from a copied .env.example.
    where = settings.local_llm_base_url if chat_model_is_local(settings) else "OpenRouter"
    logger.info("The answers come from %s at %s", chat_model_name(settings), where)
    return chat_model


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


def agent_tools(
    services: Services, extractor: FilterExtractor, retriever: LabelRetriever
) -> list[BaseTool]:
    """The agent's tools over the services, as the chat and the MCP server both serve them."""
    return build_tools(
        services.compounds, services.targets, services.complexes, extractor, retriever
    )


async def served(
    settings: Settings, tools: list[BaseTool], sessions: McpSessions
) -> list[BaseTool]:
    """The tools, or with AGENT_TOOLS=mcp the same tools over an in-memory session of the MCP
    server built from them (#42)."""
    if settings.agent_tools == "mcp":
        return await sessions.open(build_server(tools), tools)
    return tools


def open_agent(
    settings: Settings, tools: Sequence[BaseTool], canary: str, model: ChatModel | None = None
) -> ChatAgent:
    """The answering agent over the configured chat model, or over the `model` a user picked."""
    return ChatAgent(
        get_answer_model(settings, model),
        tools,
        canary=canary,
        max_steps=settings.chat_max_steps,
        timeout_seconds=settings.chat_timeout_seconds,
    )


def guarded_chat(
    settings: Settings, check: InputCheck, agent: ChatAgent, source_check_model: BaseChatModel
) -> GuardedChat:
    """The `agent` behind the guard: `check` sorts each message before the agent sees it, and
    `source_check_model` checks the answer against the results it cites."""
    return GuardedChat(
        check,
        agent,
        source_check=ChatModelSourceCheck(source_check_model),
        timeout_seconds=settings.llm_timeout_seconds,
    )


def open_model_choices(
    settings: Settings,
    default_chat: GuardedChat,
    guarded: Callable[[ChatAgent], GuardedChat],
    tools: Sequence[BaseTool],
    checked_by: Callable[[ChatModel, ChatModel], Awaitable[GuardedChat]],
    canary: str,
) -> ModelChoices[GuardedChat]:
    """The models a user may pick to write the answers (#37) and to check the messages (#363).
    With the decision model checking, a picked model only writes the answer and the guard's
    checks stay on the configured models they were measured with; with LOCAL_LLM_MODEL or the
    answering model, that model runs all three checks."""
    checkers, default_checker = open_checkers(settings)

    async def build(model: ChatModel, checker: CheckerId) -> GuardedChat:
        match checker:
            case "decision":
                return guarded(open_agent(settings, tools, canary, model))
            case "local":
                local = ChatModel(name=settings.local_llm_model or "", local=True)
                return await checked_by(model, local)
            case "answer":
                return await checked_by(model, model)

    return ModelChoices(
        ChatModel(name=chat_model_name(settings), local=chat_model_is_local(settings)),
        default_chat,
        cloud=cloud_model_choices(settings),
        local_names=partial(local_model_names, settings),
        checkers=checkers,
        default_checker=default_checker,
        build=build,
    )


def open_checkers(settings: Settings) -> tuple[list[Checker], CheckerId]:
    """The tested models that may check the messages, and the one that checks them in the
    default chat: the decision model online (#226), otherwise LOCAL_LLM_MODEL when it is the chat
    model (gpt-oss-20b offline), otherwise the chat model itself."""
    checkers: list[Checker] = []
    decision_model = online_decision_model(settings)
    if decision_model is not None:
        local = settings.local_decision_base_url is not None
        checkers.append(Checker(id="decision", name=decision_model.model, local=local))
    if settings.local_llm_base_url and settings.local_llm_model:
        checkers.append(Checker(id="local", name=settings.local_llm_model, local=True))
    if decision_model is not None:
        return checkers, "decision"
    return checkers, "local" if chat_model_is_local(settings) else "answer"


async def open_chat_checked_by(
    settings: Settings,
    model: ChatModel,
    checks_model: ChatModel,
    services: Services,
    retriever: LabelRetriever,
    sessions: McpSessions,
    canary: str,
) -> GuardedChat:
    """A chat in which `model` writes the answer and `checks_model` sorts the message, extracts
    the label filters and checks the answer, so a local pick of both makes no cloud call (#363)
    unless the instance embeds in the cloud.
    Its label filter needs tools of its own, so with AGENT_TOOLS=mcp it opens an MCP session of
    its own too (#380)."""
    checker = get_chat_model(settings, checks_model)
    extractor = FilterExtractor(checker, services.compounds, services.labels)
    tools = await served(settings, agent_tools(services, extractor, retriever), sessions)
    return guarded_chat(
        settings,
        ChatModelInputCheck(checker),
        open_agent(settings, tools, canary, model),
        get_source_check_model(settings, checks_model),
    )


@dataclass(frozen=True)
class ChatParts:
    """The label search and the guarded chat over it, with the parts the routes show."""

    embeddings: Embeddings
    retriever: LabelRetriever
    extractor: FilterExtractor
    agent: ChatAgent
    chat: GuardedChat
    model_choices: ModelChoices[GuardedChat]


async def open_chat(
    settings: Settings,
    services: Services,
    index: LabelIndex,
    chat_model: BaseChatModel,
    sessions: McpSessions,
) -> ChatParts:
    """The default chat over the configured models, and the chats a user may pick instead.
    A pick checked by the decision model shares the default chat's tools and checks."""
    embeddings = get_embeddings(settings)
    retriever = open_label_retriever(settings, index, embeddings)
    extractor = open_filter_extractor(settings, chat_model, services.compounds, services.labels)
    tools = await served(settings, agent_tools(services, extractor, retriever), sessions)
    canary = secrets.token_hex(16)
    guarded = partial(
        guarded_chat,
        settings,
        open_input_check(settings, chat_model),
        source_check_model=get_source_check_model(settings),
    )
    agent = open_agent(settings, tools, canary)
    chat = guarded(agent)
    checked_by = partial(
        open_chat_checked_by,
        settings,
        services=services,
        retriever=retriever,
        sessions=sessions,
        canary=canary,
    )
    return ChatParts(
        embeddings=embeddings,
        retriever=retriever,
        extractor=extractor,
        agent=agent,
        chat=chat,
        model_choices=open_model_choices(settings, chat, guarded, tools, checked_by, canary),
    )
