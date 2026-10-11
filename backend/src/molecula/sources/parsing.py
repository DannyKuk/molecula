import httpx2
from pydantic import BaseModel, ValidationError

from molecula.sources.errors import SourceFormatError


def parse[M: BaseModel](response: httpx2.Response, model: type[M]) -> M:
    """The response body as `model`; SourceFormatError if it has another shape."""
    try:
        return model.model_validate_json(response.content)
    except ValidationError as error:
        raise SourceFormatError(f"{response.request.url}: unexpected response shape") from error
