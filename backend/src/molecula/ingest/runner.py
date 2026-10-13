import logging
import sqlite3
from collections.abc import Callable, Iterator, Sequence
from contextlib import closing, contextmanager
from dataclasses import dataclass, field
from typing import Protocol

from molecula.config import Settings
from molecula.sources.errors import SourceError, SourceUnavailable
from molecula.sources.http import SourceClient
from molecula.store.db import connect
from molecula.store.http_cache import HttpCache

logger = logging.getLogger(__name__)


class Named(Protocol):
    @property
    def name(self) -> str: ...


@dataclass
class StepReport:
    """What an ingest step couldn't do: the items that failed, with the reason, and the items
    left untried after a source stopped answering."""

    failures: dict[str, str] = field(default_factory=dict)
    not_attempted: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not (self.failures or self.not_attempted)


def run_step[T: Named, R](
    items: Sequence[T],
    ingest_one: Callable[[T], R],
    report: StepReport,
    *,
    catch: tuple[type[Exception], ...] = (SourceError,),
) -> list[R]:
    """Ingest every item in turn and return the results of those that succeeded.

    An item that raises one of `catch` is recorded in `report.failures` and skipped; the others
    are still ingested. When a source stops answering, the run stops too, since more requests
    would only prolong a block, and the remaining items go to `report.not_attempted`.
    """
    results = []
    for position, item in enumerate(items):
        try:
            result = ingest_one(item)
        except catch as error:
            logger.warning("%s: %s", item.name, error)
            report.failures[item.name] = str(error)
            if isinstance(error, SourceUnavailable):
                report.not_attempted = [later.name for later in items[position + 1 :]]
                break
        else:
            results.append(result)
    return results


@contextmanager
def store_and_sources(settings: Settings) -> Iterator[tuple[sqlite3.Connection, SourceClient]]:
    """The store connection and a source client that caches in it, both closed afterwards."""
    with (
        closing(connect(settings.db_path)) as conn,
        closing(SourceClient(HttpCache(conn), offline=settings.offline)) as http,
    ):
        yield conn, http


def log_failures(report: StepReport, source: str) -> None:
    for name, reason in report.failures.items():
        logger.error("  failed: %s: %s", name, reason)
    if report.not_attempted:
        logger.error(
            "stopped because %s stopped answering; %d compounds not attempted. "
            "Re-run later: what is fetched so far is served from the cache.",
            source,
            len(report.not_attempted),
        )
