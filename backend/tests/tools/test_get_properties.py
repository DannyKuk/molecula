from typing import Any

import pytest
from langchain_core.tools import StructuredTool

from molecula.schemas.tools import DrugNotSupported, DrugProperties, InvalidArguments
from molecula.tools.get_properties import get_properties_tool
from tool_fakes import GLEEVEC_SUGGESTION, IMATINIB, FakeCompoundService, call_tool


@pytest.fixture
def tool(compounds: FakeCompoundService) -> StructuredTool:
    return get_properties_tool(compounds)


@pytest.mark.parametrize("drug", ["Gleevec", "imatinib mesylate", "IMATINIB"])
def test_name_brand_or_salt_name_gets_the_pubchem_properties(
    tool: StructuredTool, drug: str
) -> None:
    message = call_tool(tool, {"drug": drug})

    assert message.status == "success"
    assert message.artifact == DrugProperties(query=drug, compound=IMATINIB)


def test_properties_carry_their_pubchem_source(tool: StructuredTool) -> None:
    message = call_tool(tool, {"drug": "Gleevec"})

    assert isinstance(message.artifact, DrugProperties)
    assert message.artifact.compound.source == "pubchem"
    assert message.artifact.compound.source_url == "https://pubchem.ncbi.nlm.nih.gov/compound/5291"
    assert '"source_url":"https://pubchem.ncbi.nlm.nih.gov/compound/5291"' in str(message.content)


def test_unknown_name_is_not_supported_with_suggestions(tool: StructuredTool) -> None:
    message = call_tool(tool, {"drug": "Gleevek"})

    assert message.status == "success"
    assert message.artifact == DrugNotSupported(query="Gleevek", suggestions=[GLEEVEC_SUGGESTION])


@pytest.mark.parametrize(
    ("args", "error"),
    [
        ({"drug": ""}, "drug: String should have at least 1 character"),
        ({"drug": "x" * 101}, "drug: String should have at most 100 characters"),
        ({"drug": "<imatinib>"}, "drug: Value error, name may contain only letters"),
        ({"name": "imatinib"}, "drug: Field required"),
    ],
)
def test_bad_argument_is_a_readable_error_result(
    tool: StructuredTool, compounds: FakeCompoundService, args: dict[str, Any], error: str
) -> None:
    message = call_tool(tool, args)

    assert message.status == "error"
    [problem] = InvalidArguments.model_validate_json(str(message.content)).errors
    assert problem.startswith(error)
    assert compounds.resolved == []
