from fake_llm import ScriptedChatModel
from molecula.agent.tool_registry import build_tools
from molecula.schemas.tools import DrugTargetList
from tool_fakes import FakeCompoundService, FakeTargetService, call_tool


def test_registry_builds_the_drug_tools_over_the_services() -> None:
    tools = build_tools(FakeCompoundService(), FakeTargetService())

    assert [tool.name for tool in tools] == [
        "resolve_drug",
        "get_properties",
        "get_targets",
        "compare_drugs",
    ]
    assert all(tool.description for tool in tools)


def test_tools_bind_to_a_chat_model() -> None:
    model = ScriptedChatModel(script=[])

    model.bind_tools(build_tools(FakeCompoundService(), FakeTargetService()))

    assert model.bound_tools == ["resolve_drug", "get_properties", "get_targets", "compare_drugs"]


def test_registered_tool_calls_its_service() -> None:
    targets = FakeTargetService()
    get_targets = build_tools(FakeCompoundService(), targets)[2]

    message = call_tool(get_targets, {"drug": "Gleevec"})

    assert isinstance(message.artifact, DrugTargetList)
    assert targets.asked == [5291]
