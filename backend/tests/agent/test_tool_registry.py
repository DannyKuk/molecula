from langchain_core.tools import BaseTool

from fake_llm import ScriptedChatModel
from molecula.agent.tool_registry import build_tools
from molecula.schemas.tools import DrugTargetList, LabelPassages
from tool_fakes import (
    FakeCompoundService,
    FakeFilterExtractor,
    FakeLabelRetriever,
    FakeTargetService,
    call_tool,
)

TOOL_NAMES = ["resolve_drug", "get_properties", "get_targets", "search_labels", "compare_drugs"]


def tools(targets: FakeTargetService | None = None) -> list[BaseTool]:
    return build_tools(
        FakeCompoundService(),
        targets or FakeTargetService(),
        FakeFilterExtractor(),
        FakeLabelRetriever(),
    )


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
    get_targets = tools(targets)[2]

    message = call_tool(get_targets, {"drug": "Gleevec"})

    assert isinstance(message.artifact, DrugTargetList)
    assert targets.asked == [5291]


def test_registered_label_search_searches() -> None:
    search_labels = tools()[3]

    message = call_tool(search_labels, {"question": "How does imatinib work?"})

    assert isinstance(message.artifact, LabelPassages)
