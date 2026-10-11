"""The scripted fake model that agent tests (#16) drive instead of a real LLM."""

import asyncio

import pytest
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage
from langchain_core.messages.ai import UsageMetadata
from langchain_core.tools import tool

from fake_llm import ScriptedChatModel, answer_message, tool_call_message


@tool
def compound_lookup(name: str) -> str:
    """Look up a compound by name."""
    return f"{name}: found"


def run_tool_loop(model: ScriptedChatModel, question: str) -> list[AIMessage]:
    """The smallest agent loop: call the model, run any tool it asks for, repeat."""
    bound = model.bind_tools([compound_lookup])
    history = [HumanMessage(question)]
    replies = []
    while True:
        reply = bound.invoke(history)
        replies.append(reply)
        history.append(reply)
        if not reply.tool_calls:
            return replies
        for call in reply.tool_calls:
            history.append(
                ToolMessage(compound_lookup.invoke(call["args"]), tool_call_id=call["id"])
            )


def test_scripts_a_tool_call_then_a_final_answer() -> None:
    model = ScriptedChatModel(
        script=[
            tool_call_message("compound_lookup", {"name": "imatinib"}, call_id="call_7"),
            answer_message("Imatinib is supported."),
        ]
    )

    first, final = run_tool_loop(model, "hi")

    assert first.tool_calls == [
        {
            "name": "compound_lookup",
            "args": {"name": "imatinib"},
            "id": "call_7",
            "type": "tool_call",
        }
    ]
    assert final.content == "Imatinib is supported."
    assert model.bound_tools == ["compound_lookup"]
    tool_result = model.received[1][-1]
    assert isinstance(tool_result, ToolMessage)
    assert (tool_result.content, tool_result.tool_call_id) == ("imatinib: found", "call_7")


def test_every_reply_carries_token_usage() -> None:
    own_usage = UsageMetadata(input_tokens=100, output_tokens=1, total_tokens=101)
    model = ScriptedChatModel(
        script=[answer_message("a"), AIMessage(content="b", usage_metadata=own_usage)]
    )

    first = model.invoke("hi")
    second = model.invoke("hi")

    assert first.usage_metadata == {"input_tokens": 12, "output_tokens": 8, "total_tokens": 20}
    assert second.usage_metadata == own_usage


def test_streams_text_word_by_word_with_usage_at_the_end() -> None:
    model = ScriptedChatModel(script=[answer_message("Imatinib targets ABL1.")])

    chunks = list(model.stream("hi"))

    assert [c.content for c in chunks] == ["Imatinib", " ", "targets", " ", "ABL1.", ""]
    assert all(c.usage_metadata is None for c in chunks[:-1])
    merged = sum(chunks[1:], chunks[0])
    assert merged.content == "Imatinib targets ABL1."
    assert merged.usage_metadata == model.usage


def test_streamed_tool_calls_merge_back_into_tool_calls() -> None:
    model = ScriptedChatModel(
        script=[tool_call_message("compound_lookup", {"name": "aspirin"}, call_id="call_1")]
    )

    chunks = list(model.stream("hi"))
    merged = sum(chunks[1:], chunks[0])

    assert merged.tool_calls == [
        {
            "name": "compound_lookup",
            "args": {"name": "aspirin"},
            "id": "call_1",
            "type": "tool_call",
        }
    ]


def test_works_async() -> None:
    model = ScriptedChatModel(script=[answer_message("one"), answer_message("two words")])

    async def invoke_then_stream() -> tuple[AIMessage, list[AIMessageChunk]]:
        return await model.ainvoke("hi"), [chunk async for chunk in model.astream("hi")]

    reply, chunks = asyncio.run(invoke_then_stream())

    assert reply.content == "one"
    assert "".join(str(c.content) for c in chunks) == "two words"


def test_calling_past_the_end_of_the_script_fails_loudly() -> None:
    model = ScriptedChatModel(script=[answer_message("only one")])
    model.invoke("hi")

    with pytest.raises(AssertionError, match="only 1 messages"):
        model.invoke("hi again")
