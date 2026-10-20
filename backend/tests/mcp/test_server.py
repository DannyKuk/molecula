import asyncio
import json
from typing import Any

from langchain_core.tools import BaseTool
from mcp.server.fastmcp import FastMCP
from mcp.shared.memory import create_connected_server_and_client_session
from mcp.types import CallToolResult, TextContent, Tool

from molecula.agent.tool_registry import build_tools
from molecula.mcp.server import build_server
from molecula.schemas.chat import Source
from molecula.schemas.labels import SectionGroup
from molecula.schemas.retrieval import LabelFilter, LabelQuery
from molecula.schemas.tools import CitedTarget, DrugNotSupported, DrugTargetList
from tool_fakes import (
    ABL1,
    GLEEVEC_SUGGESTION,
    IMATINIB,
    IMATINIB_SIDE_EFFECTS,
    FakeComplexService,
    FakeCompoundService,
    FakeFilterExtractor,
    FakeLabelRetriever,
    FakeTargetService,
    cited,
    drug_filter,
)

SIDE_EFFECTS = "What are the side effects of Gleevec?"
STORAGE = "How is Gleevec stored?"
IMATINIB_STORAGE = IMATINIB_SIDE_EFFECTS.model_copy(
    update={"id": "gleevec:storage:0", "section": "storage", "text": "Store at 25 °C."}
)
PUBCHEM_IMATINIB = "https://pubchem.ncbi.nlm.nih.gov/compound/5291"


class FailingFilterExtractor:
    def filter_for(
        self, question: str, *, drug: str | None = None, section: SectionGroup | None = None
    ) -> LabelFilter:
        raise RuntimeError("the chat model is down")


def agent_tools(extractor: Any = None) -> list[BaseTool]:
    if extractor is None:
        extractor = FakeFilterExtractor()
        for question in [SIDE_EFFECTS, STORAGE]:
            extractor.filters[question] = LabelFilter(
                extracted=LabelQuery(substances=["Gleevec"]),
                drugs=[drug_filter("Gleevec", IMATINIB, ["gleevec"])],
            )
    retriever = FakeLabelRetriever()
    retriever.chunks_by_question[STORAGE] = [IMATINIB_STORAGE]
    return build_tools(
        FakeCompoundService(), FakeTargetService(), FakeComplexService(), extractor, retriever
    )


def numbering_server() -> FastMCP:
    return build_server(agent_tools(), number_sources=True)


def list_tools(server: FastMCP) -> list[Tool]:
    async def listing() -> list[Tool]:
        async with create_connected_server_and_client_session(server) as session:
            return (await session.list_tools()).tools

    return asyncio.run(listing())


def call(server: FastMCP, name: str, args: dict[str, Any]) -> CallToolResult:
    async def calling() -> CallToolResult:
        async with create_connected_server_and_client_session(server) as session:
            return await session.call_tool(name, args)

    return asyncio.run(calling())


def calls_in_one_session(
    server: FastMCP, *requests: tuple[str, dict[str, Any]]
) -> list[CallToolResult]:
    async def calling() -> list[CallToolResult]:
        async with create_connected_server_and_client_session(server) as session:
            return [await session.call_tool(name, args) for name, args in requests]

    return asyncio.run(calling())


def text_of(result: CallToolResult) -> str:
    [content] = result.content
    assert isinstance(content, TextContent)
    return content.text


def test_every_agent_tool_is_listed_with_its_docstring_and_argument_schema() -> None:
    tools = agent_tools()

    listed = list_tools(build_server(tools))

    assert [tool.name for tool in listed] == [tool.name for tool in tools]
    for served, tool in zip(listed, tools, strict=True):
        assert served.description == tool.description
        assert served.inputSchema == tool.tool_call_schema.model_json_schema()


def test_the_argument_schema_keeps_the_limits_the_agent_has() -> None:
    listed = {tool.name: tool for tool in list_tools(build_server(agent_tools()))}

    drugs = listed["compare_drugs"].inputSchema["properties"]["drugs"]
    assert (drugs["minItems"], drugs["maxItems"]) == (2, 4)
    assert listed["search_labels"].inputSchema["required"] == ["question"]


def test_a_call_returns_what_the_service_found() -> None:
    result = call(build_server(agent_tools()), "get_targets", {"drug": "Gleevec"})

    assert not result.isError
    assert result.structuredContent is None
    expected = DrugTargetList(
        query="Gleevec", cid=5291, name="imatinib", targets=[CitedTarget(**ABL1.model_dump())]
    )
    assert json.loads(text_of(result)) == expected.model_dump(mode="json")


def test_a_label_search_returns_the_cited_passages_but_not_the_retrieval() -> None:
    result = call(build_server(agent_tools()), "search_labels", {"question": SIDE_EFFECTS})

    found = json.loads(text_of(result))
    assert found["drugs"] == ["imatinib"]
    assert found["passages"] == [cited(IMATINIB_SIDE_EFFECTS, 1).model_dump(mode="json")]
    assert "retrieval" not in found


def test_a_drug_molecula_doesnt_know_is_a_result_not_an_error() -> None:
    result = call(build_server(agent_tools()), "get_properties", {"drug": "Gleevek"})

    assert not result.isError
    expected = DrugNotSupported(query="Gleevek", suggestions=[GLEEVEC_SUGGESTION])
    assert json.loads(text_of(result)) == expected.model_dump(mode="json")


def test_arguments_that_fail_the_schema_come_back_as_an_error_result() -> None:
    result = call(build_server(agent_tools()), "compare_drugs", {"drugs": ["imatinib"]})

    assert result.isError
    assert "drugs" in text_of(result)
    assert "at least 2 items" in text_of(result)


def test_a_tool_that_fails_comes_back_as_an_error_result() -> None:
    server = build_server(agent_tools(FailingFilterExtractor()))

    result = call(server, "search_labels", {"question": SIDE_EFFECTS})

    assert result.isError
    assert "search_labels" in text_of(result)


def test_numbered_sources_fill_every_ref_and_keep_a_sources_number_across_calls() -> None:
    resolved, targets, properties, labels = calls_in_one_session(
        numbering_server(),
        ("resolve_drug", {"name": "Gleevec"}),
        ("get_targets", {"drug": "Gleevec"}),
        ("get_properties", {"drug": "imatinib"}),
        ("search_labels", {"question": SIDE_EFFECTS}),
    )

    assert json.loads(text_of(resolved))["ref"] == 1
    assert [target["ref"] for target in json.loads(text_of(targets))["targets"]] == [2]
    assert json.loads(text_of(properties))["ref"] == 1
    assert [passage["ref"] for passage in json.loads(text_of(labels))["passages"]] == [3]


def test_two_label_searches_in_one_session_never_share_a_number() -> None:
    first, second, again = calls_in_one_session(
        numbering_server(),
        ("search_labels", {"question": SIDE_EFFECTS}),
        ("search_labels", {"question": STORAGE}),
        ("search_labels", {"question": SIDE_EFFECTS}),
    )

    refs = [
        [passage["ref"] for passage in json.loads(text_of(result))["passages"]]
        for result in [first, second, again]
    ]
    assert refs == [[1], [2], [1]]


def test_each_session_numbers_its_sources_from_one() -> None:
    server = numbering_server()

    [first] = calls_in_one_session(server, ("get_targets", {"drug": "Gleevec"}))
    [second] = calls_in_one_session(server, ("get_properties", {"drug": "Gleevec"}))

    assert json.loads(text_of(first))["targets"][0]["ref"] == 1
    assert json.loads(text_of(second))["ref"] == 1


def test_the_structured_content_is_the_result_with_its_sources() -> None:
    [resolved, labels] = calls_in_one_session(
        numbering_server(),
        ("resolve_drug", {"name": "Gleevec"}),
        ("search_labels", {"question": SIDE_EFFECTS}),
    )

    assert resolved.structuredContent is not None
    assert resolved.structuredContent.pop("sources") == [
        Source(kind="pubchem", name="imatinib", url=PUBCHEM_IMATINIB, ref=1).model_dump(mode="json")
    ]
    assert resolved.structuredContent == json.loads(text_of(resolved))
    assert labels.structuredContent is not None
    assert labels.structuredContent["sources"] == [
        Source(
            kind="dailymed",
            name="Gleevec",
            url=IMATINIB_SIDE_EFFECTS.url,
            section="adverse_reactions",
            effective_time=IMATINIB_SIDE_EFFECTS.effective_time,
            ref=2,
        ).model_dump(mode="json")
    ]


def test_with_numbered_sources_an_unknown_drug_is_still_a_result_with_no_sources() -> None:
    [result] = calls_in_one_session(numbering_server(), ("get_properties", {"drug": "Gleevek"}))

    assert not result.isError
    expected = DrugNotSupported(query="Gleevek", suggestions=[GLEEVEC_SUGGESTION])
    assert json.loads(text_of(result)) == expected.model_dump(mode="json")
    assert result.structuredContent == {**expected.model_dump(mode="json"), "sources": []}


def test_with_numbered_sources_failures_are_still_error_results() -> None:
    [invalid] = calls_in_one_session(numbering_server(), ("compare_drugs", {"drugs": ["imatinib"]}))
    server = build_server(agent_tools(FailingFilterExtractor()), number_sources=True)
    [failed] = calls_in_one_session(server, ("search_labels", {"question": SIDE_EFFECTS}))

    assert invalid.isError
    assert "at least 2 items" in text_of(invalid)
    assert failed.isError
    assert "search_labels" in text_of(failed)
