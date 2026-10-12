from typing import Any

import pytest
from langchain_core.tools import StructuredTool

from molecula.schemas.tools import (
    DrugComparison,
    DrugNotSupported,
    DrugProperties,
    InvalidArguments,
)
from molecula.tools.compare_drugs import compare_drugs_tool
from tool_fakes import (
    FLUTICASONE,
    GLEEVEC_SUGGESTION,
    IBUPROFEN,
    IMATINIB,
    FakeCompoundService,
    call_tool,
)


@pytest.fixture
def tool(compounds: FakeCompoundService) -> StructuredTool:
    return compare_drugs_tool(compounds)


def test_drugs_are_side_by_side_in_the_order_asked(tool: StructuredTool) -> None:
    message = call_tool(tool, {"drugs": ["Advil", "imatinib mesylate"]})

    assert message.status == "success"
    assert message.artifact == DrugComparison(
        drugs=[
            DrugProperties(query="Advil", compound=IBUPROFEN),
            DrugProperties(query="imatinib mesylate", compound=IMATINIB),
        ]
    )


def test_unsupported_drug_is_reported_in_its_place(tool: StructuredTool) -> None:
    message = call_tool(tool, {"drugs": ["Gleevec", "Gleevek", "fluticasone"]})

    assert message.status == "success"
    assert message.artifact == DrugComparison(
        drugs=[
            DrugProperties(query="Gleevec", compound=IMATINIB),
            DrugNotSupported(query="Gleevek", suggestions=[GLEEVEC_SUGGESTION]),
            DrugProperties(query="fluticasone", compound=FLUTICASONE),
        ]
    )


def test_four_drugs_are_compared(tool: StructuredTool) -> None:
    message = call_tool(tool, {"drugs": ["Gleevec", "Advil", "fluticasone", "notadrug"]})

    assert isinstance(message.artifact, DrugComparison)
    assert [drug.status for drug in message.artifact.drugs] == [
        "found",
        "found",
        "found",
        "not_supported",
    ]


@pytest.mark.parametrize(
    ("args", "error"),
    [
        ({"drugs": ["Gleevec"]}, "drugs: List should have at least 2 items"),
        ({"drugs": ["a", "b", "c", "d", "e"]}, "drugs: List should have at most 4 items"),
        ({"drugs": ["Gleevec", ""]}, "drugs.1: String should have at least 1 character"),
        ({"drugs": ["Gleevec", "Advil;"]}, "drugs.1: Value error, name may contain only"),
        ({"drugs": "Gleevec, Advil"}, "drugs: Input should be a valid list"),
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
