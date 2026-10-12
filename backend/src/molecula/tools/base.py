import inspect
from collections.abc import Callable
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ValidationError

from molecula.schemas.compounds import Resolution
from molecula.schemas.tools import DrugNotSupported, InvalidArguments


def build_tool(func: Callable[..., BaseModel], args_schema: type[BaseModel]) -> StructuredTool:
    """A LangChain tool named after `func` and described by its docstring.

    The model reads the result as JSON; the typed result travels as the tool message's artifact.
    Arguments that fail `args_schema` come back as an `InvalidArguments` result, not an exception.
    """

    def run(**arguments: Any) -> tuple[str, BaseModel]:
        result = func(**arguments)
        return result.model_dump_json(), result

    return StructuredTool.from_function(
        run,
        name=func.__name__,
        description=inspect.getdoc(func),
        args_schema=args_schema,
        response_format="content_and_artifact",
        handle_validation_error=describe_invalid_arguments,
    )


def describe_invalid_arguments(error: ValidationError) -> str:
    """One line per problem, named by the argument (`drugs.1` is the second drug)."""
    problems = [
        f"{'.'.join(str(part) for part in detail['loc'])}: {detail['msg']}"
        for detail in error.errors()
    ]
    return InvalidArguments(errors=problems).model_dump_json()


def not_supported(resolution: Resolution) -> DrugNotSupported:
    return DrugNotSupported(query=resolution.query, suggestions=resolution.suggestions)
