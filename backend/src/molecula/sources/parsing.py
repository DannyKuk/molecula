import httpx2
from pydantic import BaseModel, ValidationError

from molecula.sources.errors import SourceFormatError
from molecula.sources.http import discard_cached


def parse[M: BaseModel](response: httpx2.Response, model: type[M]) -> M:
    """The response body as `model`; SourceFormatError if it has another shape, and then the body
    is dropped from the cache so the next call asks the source again."""
    try:
        return model.model_validate_json(response.content)
    except ValidationError as error:
        discard_cached(response)
        raise SourceFormatError(f"{response.request.url}: unexpected response shape") from error
