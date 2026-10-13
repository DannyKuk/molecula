from typing import Any

import pytest
from langchain_core.tools import BaseTool

from fake_llm import ScriptedChatModel
from molecula.agent.tool_registry import build_tools
from molecula.schemas.tools import DrugTargetList, LabelPassages
from molecula.tools.base import progress_of
from tool_fakes import (
    FakeComplexService,
    FakeCompoundService,
    FakeFilterExtractor,
    FakeLabelRetriever,
    FakeTargetService,
    call_tool,
)

TOOL_NAMES = [
    "resolve_drug",
    "get_properties",
    "get_targets",
    "get_complex",
    "search_labels",
    "compare_drugs",
]


def tools(targets: FakeTargetService | None = None) -> list[BaseTool]:
    return build_tools(
        FakeCompoundService(),
        targets or FakeTargetService(),
        FakeComplexService(),
        FakeFilterExtractor(),
        FakeLabelRetriever(),
    )


def named(registered: list[BaseTool], name: str) -> BaseTool:
    return next(tool for tool in registered if tool.name == name)


def test_registry_builds_the_tools_over_the_services() -> None:
    registered = tools()

    assert [tool.name for tool in registered] == TOOL_NAMES
    assert all(tool.description for tool in registered)


def test_tools_bind_to_a_chat_model() -> None:
    model = ScriptedChatModel(script=[])

    model.bind_tools(tools())

    assert model.bound_tools == TOOL_NAMES


def test_registered_tool_calls_its_service() -> None:
    targets = FakeTargetService()
    get_targets = named(tools(targets), "get_targets")

    message = call_tool(get_targets, {"drug": "Gleevec"})

    assert isinstance(message.artifact, DrugTargetList)
    assert targets.asked == [5291]


def test_registered_label_search_searches() -> None:
    search_labels = named(tools(), "search_labels")

    message = call_tool(search_labels, {"question": "How does imatinib work?"})

    assert isinstance(message.artifact, LabelPassages)


def test_every_registered_tool_has_its_own_progress_text() -> None:
    without_progress = [tool.name for tool in tools() if progress_of(tool) is None]

    assert without_progress == []


@pytest.mark.parametrize(
    ("name", "args", "expected"),
    [
        ("resolve_drug", {"name": "Gleevec"}, "Looking up Gleevec"),
        ("get_properties", {"drug": "imatinib"}, "Getting the properties of imatinib"),
        ("get_targets", {"drug": "imatinib"}, "Finding the targets of imatinib"),
        ("search_labels", {"question": "Q?", "drug": "imatinib"}, "Searching the imatinib label"),
        ("search_labels", {"question": "Q?"}, "Searching the drug labels"),
        ("compare_drugs", {"drugs": ["imatinib", "Advil"]}, "Comparing imatinib, Advil"),
        ("get_targets", {}, "Finding the targets of the drug"),
    ],
)
def test_progress_text_names_what_the_call_is_doing(
    name: str, args: dict[str, Any], expected: str
) -> None:
    progress = progress_of(next(tool for tool in tools() if tool.name == name))

    assert progress is not None
    assert progress(args) == expected
