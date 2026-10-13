import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from langchain_core.language_models import BaseChatModel

from molecula.agent.agent import ChatAgent
from molecula.agent.llm import LLMConfigError, get_chat_model
from molecula.agent.tool_registry import build_tools
from molecula.api import chat, drugs, health
from molecula.config import Settings, get_settings
from molecula.guard.chat import GuardedChat
from molecula.guard.safety import ChatModelInputCheck
from molecula.guard.validation import readable_validation_error
from molecula.rag.embeddings import embedding_model_id, get_embeddings
from molecula.rag.filters import FilterExtractor
from molecula.rag.retriever import LabelRetriever
from molecula.services.complexes import ComplexService
from molecula.services.compounds import CompoundService
from molecula.services.labels import LabelService
from molecula.services.targets import TargetService
from molecula.store.compounds import CompoundStore
from molecula.store.db import connect
from molecula.store.index import LabelIndex
from molecula.store.labels import LabelStore
from molecula.store.structures import ComplexFiles, ConformerFiles
from molecula.store.targets import TargetStore

logger = logging.getLogger(__name__)


def open_store(settings: Settings) -> sqlite3.Connection:
    """The built store, or an empty one in memory until the first build or fetch.

    `connect` would create the file, and an empty store file would stop `ingest fetch` (#35) from
    downloading the data, so the app never creates it.
    """
    if settings.db_path.exists():
        return connect(settings.db_path)
    logger.warning("No store at %s yet; no drug is supported until it is built", settings.db_path)
    return connect(Path(":memory:"))


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


def open_chat_model(settings: Settings) -> BaseChatModel | None:
    """The chat model, or None while none is configured: the chat and the label search are then
    off, and the data routes still work."""
    try:
        return get_chat_model(settings)
    except LLMConfigError as error:
        logger.warning("Label search and chat are off: %s", error)
        return None


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    conn = open_store(settings)
    compounds = CompoundStore(conn)
    app.state.compound_service = CompoundService(
        compounds,
        ConformerFiles(settings.conformers_dir),
        suggestion_cutoff=settings.name_suggestion_cutoff,
    )
    app.state.target_service = TargetService(TargetStore(conn), compounds)
    app.state.label_service = LabelService(LabelStore(conn), compounds)
    app.state.complex_service = ComplexService(ComplexFiles(settings.complexes_dir))
    app.state.label_retriever = None
    app.state.filter_extractor = None
    app.state.chat_agent = None
    app.state.chat = None
    index = open_label_index(settings)
    chat_model = open_chat_model(settings) if index is not None else None
    if index is not None and chat_model is not None:
        app.state.label_retriever = LabelRetriever(
            index,
            get_embeddings(settings),
            top_k=settings.retrieval_top_k,
            min_score=settings.retrieval_min_score,
            section_group_boost=settings.retrieval_section_group_boost,
        )
        app.state.filter_extractor = FilterExtractor(
            chat_model, app.state.compound_service, app.state.label_service
        )
        tools = build_tools(
            app.state.compound_service,
            app.state.target_service,
            app.state.complex_service,
            app.state.filter_extractor,
            app.state.label_retriever,
        )
        app.state.chat_agent = ChatAgent(
            chat_model,
            tools,
            max_steps=settings.chat_max_steps,
            timeout_seconds=settings.chat_timeout_seconds,
            disclaimer=app.state.label_service.disclaimer(),
        )
        app.state.chat = GuardedChat(
            ChatModelInputCheck(chat_model),
            app.state.chat_agent,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    yield
    conn.close()


app = FastAPI(title="Molecula", lifespan=lifespan)
app.add_exception_handler(RequestValidationError, readable_validation_error)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(drugs.router)
app.include_router(chat.router)
