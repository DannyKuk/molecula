import json
from typing import Any

import pytest
from langchain_core.tools import StructuredTool

from molecula.schemas.tools import DrugNotSupported, InvalidArguments, ResolvedDrug
from molecula.tools.resolve_drug import resolve_drug_tool
from tool_fakes import GLEEVEC_SUGGESTION, FakeCompoundService, call_tool


@pytest.fixture
def tool(compounds: FakeCompoundService) -> StructuredTool:
    return resolve_drug_tool(compounds)


def test_brand_resolves_to_the_generic_with_its_pubchem_page(tool: StructuredTool) -> None:
    message = call_tool(tool, {"name": "Gleevec"})

    assert message.status == "success"
    assert message.artifact == ResolvedDrug(
        query="Gleevec",
        cid=5291,
        name="imatinib",
        matched_alias="Gleevec",
        match_kind="alias",
        source="pubchem",
        source_url="https://pubchem.ncbi.nlm.nih.gov/compound/5291",
    )


def test_model_reads_the_result_as_json(tool: StructuredTool) -> None:
    message = call_tool(tool, {"name": "Gleevec"})

    assert json.loads(str(message.content)) == message.artifact.model_dump()


def test_salt_name_resolves_to_the_stored_parent(tool: StructuredTool) -> None:
    message = call_tool(tool, {"name": "imatinib mesylate"})

    assert isinstance(message.artifact, ResolvedDrug)
    assert (message.artifact.name, message.artifact.matched_alias) == ("imatinib", "imatinib")


def test_misspelled_name_is_not_supported_with_suggestions(tool: StructuredTool) -> None:
    message = call_tool(tool, {"name": "Gleevek"})

    assert message.status == "success"
    assert message.artifact == DrugNotSupported(query="Gleevek", suggestions=[GLEEVEC_SUGGESTION])


def test_unknown_name_is_not_supported(tool: StructuredTool) -> None:
    message = call_tool(tool, {"name": "notadrug"})

    assert message.artifact == DrugNotSupported(query="notadrug", suggestions=[])


@pytest.mark.parametrize(
    ("args", "error"),
    [
        ({"name": ""}, "name: String should have at least 1 character"),
        ({"name": "x" * 101}, "name: String should have at most 100 characters"),
        ({"name": "imatinib; drop"}, "name: Value error, name may contain only letters"),
        ({"name": 5}, "name: Input should be a valid string"),
        ({}, "name: Field required"),
    ],
)
def test_bad_argument_is_a_readable_error_result(
    tool: StructuredTool, compounds: FakeCompoundService, args: dict[str, Any], error: str
) -> None:
    message = call_tool(tool, args)

    assert message.status == "error"
    assert message.artifact is None
    [problem] = InvalidArguments.model_validate_json(str(message.content)).errors
    assert problem.startswith(error)
    assert compounds.resolved == []


def test_tool_is_named_and_described_for_the_model(tool: StructuredTool) -> None:
    assert tool.name == "resolve_drug"
    assert "brand" in tool.description
    assert list(tool.args) == ["name"]
