from pydantic import BaseModel


class ErrorDetail(BaseModel):
    """The body of an error response, as FastAPI's `HTTPException` writes it."""

    detail: str
