import asyncio
import json
from typing import Any

import pytest
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool

from fake_llm import ScriptedChatModel
from molecula.agent.tool_registry import build_tools, tools_over_mcp
from molecula.mcp.server import build_server
from molecula.schemas.labels import SectionGroup
from molecula.schemas.retrieval import LabelFilter, LabelQuery
from molecula.schemas.tools import DrugTargetList, LabelPassages
from molecula.schemas.usage import Usage
from molecula.tools.base import progress_of
from tool_fakes import (
    IMATINIB,
    IMATINIB_LOW_SCORE,
    FakeComplexService,
    FakeCompoundService,
    FakeFilterExtractor,
    FakeLabelRetriever,
    FakeTargetService,
    call_tool,
    drug_filter,
)

TOOL_NAMES = [
    "resolve_drug",
    "get_properties",
    "get_targets",
    "get_complex",
    "search_labels",
    "compare_drugs",
]


MECHANISM = "How does imatinib work?"
EXTRACTION = Usage(input_tokens=200, output_tokens=10, total_tokens=210, cost_usd=0.00005)


class FailingFilterExtractor:
    def filter_for(
        self, question: str, *, drug: str | None = None, section: SectionGroup | None = None
    ) -> LabelFilter:
        raise RuntimeError("the chat model is down")


def extracting_with_usage() -> FakeFilterExtractor:
    extractor = FakeFilterExtractor()
    extractor.filters[MECHANISM] = LabelFilter(
        extracted=LabelQuery(substances=["imatinib"], section_groups=["pharmacology"]),
        drugs=[drug_filter("imatinib", IMATINIB, ["gleevec"])],
        section_groups=["pharmacology"],
        extraction_usage=EXTRACTION,
    )
    return extractor


def tools(targets: FakeTargetService | None = None, extractor: Any = None) -> list[BaseTool]:
    return build_tools(
        FakeCompoundService(),
        targets or FakeTargetService(),
        FakeComplexService(),
        extractor or FakeFilterExtractor(),
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


def test_tools_over_mcp_are_the_servers_tools_with_the_local_progress_texts() -> None:
    local = tools()

    async def load() -> list[BaseTool]:
        async with tools_over_mcp(build_server(local), local) as served:
            return served

    served = asyncio.run(load())

    assert [tool.name for tool in served] == TOOL_NAMES
    assert [tool.description for tool in served] == [tool.description for tool in local]
    progress = progress_of(named(served, "get_targets"))
    assert progress is not None
    assert progress({"drug": "imatinib"}) == "Finding the targets of imatinib"


def calls_over_mcp(local: list[BaseTool], *calls: tuple[str, dict[str, Any]]) -> list[ToolMessage]:
    async def calling() -> list[ToolMessage]:
        async with tools_over_mcp(build_server(local), local) as served:
            return [
                await named(served, name).ainvoke(
                    {"type": "tool_call", "name": name, "args": args, "id": f"call_{n}"}
                )
                for n, (name, args) in enumerate(calls)
            ]

    return asyncio.run(calling())


def test_a_tool_over_mcp_gives_the_model_the_same_json_as_the_local_tool() -> None:
    local = tools()
    args = {"drug": "Gleevec"}

    [message] = calls_over_mcp(local, ("get_targets", args))

    assert message.status == "success"
    assert json.loads(message.text) == json.loads(
        str(call_tool(named(local, "get_targets"), args).content)
    )


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("resolve_drug", {"name": "Gleevec"}),
        ("get_properties", {"drug": "Gleevek"}),
        ("get_targets", {"drug": "Gleevec"}),
        ("get_complex", {"drug": "imatinib"}),
        ("compare_drugs", {"drugs": ["imatinib", "Gleevek"]}),
        ("search_labels", {"question": MECHANISM, "drug": "imatinib"}),
        ("search_labels", {"question": MECHANISM}),
    ],
)
def test_a_tool_over_mcp_returns_the_local_tools_typed_result(
    name: str, args: dict[str, Any]
) -> None:
    local = tools(extractor=extracting_with_usage())

    [message] = calls_over_mcp(local, (name, args))

    assert message.artifact == call_tool(named(local, name), args).artifact


def test_a_label_search_over_mcp_keeps_the_retrieval_and_the_filters_usage() -> None:
    [message] = calls_over_mcp(
        tools(extractor=extracting_with_usage()), ("search_labels", {"question": MECHANISM})
    )

    assert isinstance(message.artifact, LabelPassages)
    assert message.artifact.retrieval.dropped == [IMATINIB_LOW_SCORE]
    label_filter = message.artifact.retrieval.filter
    assert label_filter is not None
    assert label_filter.extraction_usage == EXTRACTION


def test_a_tool_that_fails_over_mcp_is_an_error_message_without_a_result() -> None:
    [message] = calls_over_mcp(
        tools(extractor=FailingFilterExtractor()), ("search_labels", {"question": MECHANISM})
    )

    assert message.status == "error"
    assert message.artifact is None
