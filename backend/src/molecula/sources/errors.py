class SourceError(Exception):
    """Base for every error a source client raises."""


class SourceNotFound(SourceError):
    """The source has no record for the request (HTTP 404)."""


class SourceUnavailable(SourceError):
    """The source kept throttling or failing until the retries ran out."""


class OfflineError(SourceError):
    """A request was needed while OFFLINE=1."""


class SourceResponseError(SourceError):
    """The source answered with a status the client doesn't handle."""

    def __init__(self, url: str, status: int) -> None:
        super().__init__(f"{url}: HTTP {status}")
        self.status = status
