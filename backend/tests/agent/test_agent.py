import asyncio
from collections.abc import Sequence

import httpx
import openai
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolCall

from fake_llm import ScriptedChatModel, answer_message, tool_call_message
from molecula import prompts
from molecula.agent.agent import ChatAgent
from molecula.agent.tool_registry import build_tools
from molecula.schemas.chat import (
    ChatEvent,
    ChatMessage,
    DoneEvent,
    ErrorEvent,
    RetrievalTraceEvent,
    SourcesEvent,
    StatusEvent,
    TokenEvent,
    ToolCallEvent,
    ToolResultEvent,
)
from molecula.schemas.retrieval import LabelFilter, LabelQuery
from tool_fakes import (
    IMATINIB,
    IMATINIB_LOW_SCORE,
    IMATINIB_SIDE_EFFECTS,
    FakeComplexService,
    FakeCompoundService,
    FakeFilterExtractor,
    FakeLabelRetriever,
    FakeTargetService,
    drug_filter,
)

QUESTION = [ChatMessage(role="user", content="What does imatinib target?")]
SIDE_EFFECTS = "What are the side effects of imatinib?"
WARNINGS = "What are the warnings for imatinib?"
IMATINIB_EDEMA = IMATINIB_SIDE_EFFECTS.model_copy(
    update={"id": "gleevec:adverse_reactions:1", "text": "Edema was reported in 60% of patients."}
)
IMATINIB_HEPATOTOXICITY = IMATINIB_SIDE_EFFECTS.model_copy(
    update={
        "id": "gleevec:warnings_and_cautions:0",
        "text": "Hepatotoxicity, occasionally severe, may occur.",
        "section": "warnings_and_cautions",
        "section_group": "warnings",
    }
)


def agent(
    model: ScriptedChatModel,
    *,
    extractor: FakeFilterExtractor | None = None,
    retriever: FakeLabelRetriever | None = None,
    max_steps: int = 5,
    timeout_seconds: float = 10.0,
) -> ChatAgent:
    tools = build_tools(
        FakeCompoundService(),
        FakeTargetService(),
        FakeComplexService(),
        extractor or FakeFilterExtractor(),
        retriever or FakeLabelRetriever(),
    )
    return ChatAgent(model, tools, max_steps=max_steps, timeout_seconds=timeout_seconds)


def run(chat: ChatAgent, conversation: Sequence[ChatMessage] = QUESTION) -> list[ChatEvent]:
    async def collect() -> list[ChatEvent]:
        return [event async for event in chat.stream(conversation)]

    return asyncio.run(collect())


def kinds(events: list[ChatEvent]) -> list[str]:
    """The event types in order, with runs of tokens shown once."""
    shown: list[str] = []
    for event in events:
        if not (event.type == "token" and shown and shown[-1] == "token"):
            shown.append(event.type)
    return shown


def answer(events: list[ChatEvent]) -> str:
    return "".join(event.text for event in events if isinstance(event, TokenEvent))


def label_retriever() -> FakeLabelRetriever:
    retriever = FakeLabelRetriever()
    retriever.chunks_by_question = {
        SIDE_EFFECTS: [IMATINIB_SIDE_EFFECTS, IMATINIB_EDEMA],
        WARNINGS: [IMATINIB_HEPATOTOXICITY, IMATINIB_SIDE_EFFECTS],
    }
    return retriever


def search(question: str, call_id: str) -> ToolCall:
    return {"name": "search_labels", "args": {"question": question}, "id": call_id}


def passage_refs(events: list[ChatEvent]) -> list[tuple[int, str]]:
    """(ref, chunk id) of every passage the model read, in the order the results came."""
    return [
        (passage["ref"], passage["id"])
        for event in events
        if isinstance(event, ToolResultEvent) and event.name == "search_labels"
        for passage in event.result["passages"]
    ]


def sources_event(events: list[ChatEvent]) -> SourcesEvent:
    return next(e for e in events if isinstance(e, SourcesEvent))


def provider_error(error: type[openai.APIStatusError], status: int) -> openai.APIStatusError:
    response = httpx.Response(status, request=httpx.Request("POST", "http://llm.test/chat"))
    return error("provider says no", response=response, body=None)


def test_a_tool_call_streams_its_steps_then_the_answer_then_done() -> None:
    model = ScriptedChatModel(
        script=[
            tool_call_message("get_targets", {"drug": "imatinib"}),
            answer_message("Imatinib blocks the ABL1 kinase."),
        ]
    )

    events = run(agent(model))

    assert kinds(events) == ["status", "tool_call", "tool_result", "token", "sources", "done"]
    status, call, result = events[:3]
    assert isinstance(status, StatusEvent)
    assert status.message == "Finding the targets of imatinib"
    assert isinstance(call, ToolCallEvent)
    assert (call.id, call.name, call.args) == ("call_1", "get_targets", {"drug": "imatinib"})
    assert isinstance(result, ToolResultEvent)
    assert (result.id, result.name, result.status) == ("call_1", "get_targets", "found")
    assert result.result["targets"][0]["name"] == "Tyrosine-protein kinase ABL1"
    assert answer(events) == "Imatinib blocks the ABL1 kinase."


def test_done_carries_the_token_usage_of_every_model_call() -> None:
    model = ScriptedChatModel(
        script=[tool_call_message("get_targets", {"drug": "imatinib"}), answer_message("ABL1.")]
    )

    done = run(agent(model))[-1]

    assert isinstance(done, DoneEvent)
    assert (done.usage.input_tokens, done.usage.output_tokens, done.usage.total_tokens) == (
        24,
        16,
        40,
    )
    assert not done.step_limit_reached


def test_sources_list_what_the_tools_returned_once_each() -> None:
    model = ScriptedChatModel(
        script=[
            tool_call_message("get_targets", {"drug": "imatinib"}, call_id="call_1"),
            tool_call_message("get_targets", {"drug": "Gleevec"}, call_id="call_2"),
            answer_message("ABL1."),
        ]
    )

    sources = next(e for e in run(agent(model)) if isinstance(e, SourcesEvent)).sources

    assert [(s.kind, s.name, s.url) for s in sources] == [
        (
            "chembl",
            "Tyrosine-protein kinase ABL1",
            "https://www.ebi.ac.uk/chembl/explore/target/CHEMBL1862",
        )
    ]


def test_the_system_prompt_and_the_conversation_reach_the_model() -> None:
    model = ScriptedChatModel(script=[answer_message("Simpler: it blocks one enzyme.")])
    conversation = [
        ChatMessage(role="user", content="How does imatinib work?"),
        ChatMessage(role="assistant", content="It inhibits the BCR-ABL kinase."),
        ChatMessage(role="user", content="Explain it simpler"),
    ]

    run(agent(model), conversation)

    system, *messages = model.received[0]
    assert isinstance(system, SystemMessage)
    assert system.text == prompts.load("agent/system")
    assert [(type(m), m.text) for m in messages] == [
        (HumanMessage, "How does imatinib work?"),
        (AIMessage, "It inhibits the BCR-ABL kinase."),
        (HumanMessage, "Explain it simpler"),
    ]


def test_a_provider_error_becomes_an_error_event_and_ends_the_stream() -> None:
    model = ScriptedChatModel(script=[provider_error(openai.RateLimitError, 429)])

    events = run(agent(model))

    assert len(events) == 1
    assert isinstance(events[0], ErrorEvent)
    assert "rate limit" in events[0].message


def test_a_provider_error_after_a_tool_call_keeps_the_steps_already_sent() -> None:
    model = ScriptedChatModel(
        script=[
            tool_call_message("get_targets", {"drug": "imatinib"}),
            provider_error(openai.AuthenticationError, 401),
        ]
    )

    events = run(agent(model))

    assert kinds(events) == ["status", "tool_call", "tool_result", "error"]
    error = events[-1]
    assert isinstance(error, ErrorEvent)
    assert "API key" in error.message


def test_running_out_of_time_becomes_an_error_event() -> None:
    model = ScriptedChatModel(script=[answer_message("Too late.")])

    events = run(agent(model, timeout_seconds=0))

    assert kinds(events) == ["error"]
    error = events[0]
    assert isinstance(error, ErrorEvent)
    assert "longer than 0 seconds" in error.message


def test_at_the_step_limit_the_model_answers_without_further_tool_calls() -> None:
    model = ScriptedChatModel(
        script=[
            tool_call_message("get_targets", {"drug": "imatinib"}, call_id="call_1"),
            tool_call_message(
                "get_properties",
                {"drug": "imatinib"},
                call_id="call_2",
                content="Imatinib targets ABL1; I could not look up its properties.",
            ),
        ]
    )

    events = run(agent(model, max_steps=2))

    assert kinds(events) == ["status", "tool_call", "tool_result", "token", "sources", "done"]
    assert answer(events) == "Imatinib targets ABL1; I could not look up its properties."
    done = events[-1]
    assert isinstance(done, DoneEvent)
    assert done.step_limit_reached
    last_system = model.received[1][0]
    assert last_system.text == prompts.load(
        "agent/step_limit", system_prompt=prompts.load("agent/system")
    )


def test_earlier_turns_dont_count_towards_the_step_limit() -> None:
    model = ScriptedChatModel(
        script=[tool_call_message("get_targets", {"drug": "imatinib"}), answer_message("ABL1.")]
    )
    history = [
        ChatMessage(role="user", content="What is imatinib?"),
        ChatMessage(role="assistant", content="A cancer drug."),
        ChatMessage(role="user", content="Is it a pill?"),
        ChatMessage(role="assistant", content="Yes, tablets."),
    ]

    events = run(agent(model, max_steps=2), [*history, *QUESTION])

    assert kinds(events) == ["status", "tool_call", "tool_result", "token", "sources", "done"]
    assert model.received[0][0].text == prompts.load("agent/system")


def test_a_label_search_by_drug_emits_one_retrieval_trace() -> None:
    model = ScriptedChatModel(
        script=[
            tool_call_message(
                "search_labels",
                {
                    "question": "What are the side effects of imatinib?",
                    "drug": "imatinib",
                    "section": "adverse_reactions",
                },
            ),
            answer_message("Nausea and fluid retention."),
        ]
    )

    events = run(agent(model))

    assert kinds(events) == [
        "status",
        "tool_call",
        "tool_result",
        "retrieval_trace",
        "token",
        "sources",
        "done",
    ]
    assert events[0] == StatusEvent(message="Searching the imatinib label")
    trace = events[3]
    assert isinstance(trace, RetrievalTraceEvent)
    assert trace.tool_call_id == "call_1"
    assert trace.question == "What are the side effects of imatinib?"
    assert trace.translation == []
    assert trace.filter_source == "agent"
    assert [(c.id, c.score, c.kept) for c in trace.candidates] == [
        (IMATINIB_SIDE_EFFECTS.id, IMATINIB_SIDE_EFFECTS.score, True),
        (IMATINIB_LOW_SCORE.id, IMATINIB_LOW_SCORE.score, False),
    ]
    sources = events[-2]
    assert isinstance(sources, SourcesEvent)
    assert [(s.kind, s.name, s.url, s.section) for s in sources.sources] == [
        ("dailymed", "Gleevec", IMATINIB_SIDE_EFFECTS.url, "adverse_reactions")
    ]


def test_a_label_search_without_a_drug_traces_the_filter_the_model_extracted() -> None:
    question = "Does Gleevec cause nausea?"
    extractor = FakeFilterExtractor()
    extracted = LabelFilter(
        extracted=LabelQuery(substances=["Gleevec"], section_groups=["adverse_reactions"]),
        drugs=[drug_filter("Gleevec", IMATINIB, ["gleevec"])],
        section_groups=["adverse_reactions"],
    )
    extractor.filters[question] = extracted
    model = ScriptedChatModel(
        script=[
            tool_call_message("search_labels", {"question": question}),
            answer_message("Yes, nausea is common."),
        ]
    )

    events = run(agent(model, extractor=extractor))

    traces = [e for e in events if isinstance(e, RetrievalTraceEvent)]
    assert len(traces) == 1
    assert traces[0].filter_source == "model"
    assert traces[0].filter == extracted


def test_passages_keep_unique_numbers_across_two_label_searches() -> None:
    model = ScriptedChatModel(
        script=[
            AIMessage(content="", tool_calls=[search(SIDE_EFFECTS, "call_1")]),
            AIMessage(content="", tool_calls=[search(WARNINGS, "call_2")]),
            answer_message("Nausea [1] and edema [2]; the liver can suffer [3]."),
        ]
    )

    events = run(agent(model, retriever=label_retriever()))

    assert passage_refs(events) == [
        (1, IMATINIB_SIDE_EFFECTS.id),
        (2, IMATINIB_EDEMA.id),
        (3, IMATINIB_HEPATOTOXICITY.id),
        (1, IMATINIB_SIDE_EFFECTS.id),
    ]
    sources = sources_event(events)
    assert [(s.ref, s.section) for s in sources.sources] == [
        (1, "adverse_reactions"),
        (2, "adverse_reactions"),
        (3, "warnings_and_cautions"),
    ]
    assert sources.unknown_refs == []


def test_two_label_searches_in_one_model_turn_never_share_a_number() -> None:
    model = ScriptedChatModel(
        script=[
            AIMessage(
                content="",
                tool_calls=[search(SIDE_EFFECTS, "call_1"), search(WARNINGS, "call_2")],
            ),
            answer_message("Nausea [1]."),
        ]
    )

    events = run(agent(model, retriever=label_retriever()))

    numbered = dict((chunk_id, ref) for ref, chunk_id in passage_refs(events))
    assert sorted(numbered.values()) == [1, 2, 3]
    assert {s.ref for s in sources_event(events).sources} == {1, 2, 3}


def call(name: str, args: dict[str, object], call_id: str) -> ToolCall:
    return {"name": name, "args": args, "id": call_id}


def test_every_tools_sources_are_numbered_from_one_counter() -> None:
    model = ScriptedChatModel(
        script=[
            AIMessage(content="", tool_calls=[search(SIDE_EFFECTS, "call_1")]),
            AIMessage(content="", tool_calls=[call("get_properties", {"drug": "imatinib"}, "c2")]),
            AIMessage(content="", tool_calls=[call("get_targets", {"drug": "Gleevec"}, "c3")]),
            AIMessage(
                content="",
                tool_calls=[call("compare_drugs", {"drugs": ["imatinib", "Advil"]}, "c4")],
            ),
            AIMessage(content="", tool_calls=[call("get_complex", {"drug": "imatinib"}, "c5")]),
            answer_message("Nausea [1]; 100 g/mol [3]; ABL1 [4]; ibuprofen [5]; 2HYY [6]."),
        ]
    )

    events = run(agent(model, retriever=label_retriever(), max_steps=6))

    results = {e.name: e.result for e in events if isinstance(e, ToolResultEvent)}
    assert results["get_properties"]["ref"] == 3
    assert [t["ref"] for t in results["get_targets"]["targets"]] == [4]
    assert [d["ref"] for d in results["compare_drugs"]["drugs"]] == [3, 5]
    assert results["get_complex"]["ref"] == 6
    sources = sources_event(events)
    assert [(s.kind, s.ref) for s in sources.sources] == [
        ("dailymed", 1),
        ("dailymed", 2),
        ("pubchem", 3),
        ("chembl", 4),
        ("pubchem", 5),
        ("rcsb", 6),
    ]
    assert sources.unknown_refs == []


def test_a_cited_number_no_passage_has_is_flagged() -> None:
    model = ScriptedChatModel(
        script=[
            AIMessage(content="", tool_calls=[search(SIDE_EFFECTS, "call_1")]),
            answer_message("Nausea [1], edema [2, 4] and hair loss [7]."),
        ]
    )

    sources = sources_event(run(agent(model, retriever=label_retriever())))

    assert [s.ref for s in sources.sources] == [1, 2]
    assert sources.unknown_refs == [4, 7]


def test_numbers_start_again_at_one_for_each_answer() -> None:
    conversation = [
        ChatMessage(role="user", content=SIDE_EFFECTS),
        ChatMessage(role="assistant", content="Nausea [1] and edema [2]."),
        ChatMessage(role="user", content=WARNINGS),
    ]
    model = ScriptedChatModel(
        script=[
            AIMessage(content="", tool_calls=[search(WARNINGS, "call_1")]),
            answer_message("The liver can suffer [1]."),
        ]
    )

    events = run(agent(model, retriever=label_retriever()), conversation)

    assert passage_refs(events) == [(1, IMATINIB_HEPATOTOXICITY.id), (2, IMATINIB_SIDE_EFFECTS.id)]
