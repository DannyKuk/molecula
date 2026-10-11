import logging
import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from molecula.api import drugs, health
from molecula.config import Settings, get_settings
from molecula.services.compounds import CompoundService
from molecula.store.compounds import CompoundStore
from molecula.store.db import connect
from molecula.store.structures import ConformerFiles

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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    conn = open_store(settings)
    app.state.compound_service = CompoundService(
        CompoundStore(conn), ConformerFiles(settings.conformers_dir)
    )
    yield
    conn.close()


app = FastAPI(title="Molecula", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(health.router)
app.include_router(drugs.router)
