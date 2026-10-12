import ast
import inspect
import pkgutil
from importlib import import_module

import pytest
from pydantic import BaseModel, ValidationError

from molecula import tools
from molecula.schemas.compounds import DrugName
from molecula.schemas.tools import InvalidArguments
from molecula.tools.base import describe_invalid_arguments

ALLOWED_IMPORTS = ("molecula.services", "molecula.schemas", "molecula.tools")


class TwoNames(BaseModel):
    first: DrugName
    second: DrugName


def test_every_problem_is_one_line_named_by_its_argument() -> None:
    with pytest.raises(ValidationError) as caught:
        TwoNames.model_validate({"first": "", "second": "a;b"})

    result = InvalidArguments.model_validate_json(describe_invalid_arguments(caught.value))
    assert result.errors == [
        "first: String should have at least 1 character",
        "second: Value error, name may contain only letters, digits, spaces and the "
        "characters - , ( ) ' + .",
    ]


def test_tools_reach_only_services_and_schemas() -> None:
    for module_info in pkgutil.iter_modules(tools.__path__):
        module = import_module(f"molecula.tools.{module_info.name}")
        imports = {
            node.module
            for node in ast.walk(ast.parse(inspect.getsource(module)))
            if isinstance(node, ast.ImportFrom) and node.module
        }

        molecula_imports = {name for name in imports if name.startswith("molecula")}
        assert all(name.startswith(ALLOWED_IMPORTS) for name in molecula_imports), module
