import pytest

from fake_llm import CANARY
from molecula.guard.canary import CanaryWatch, PromptLeaked
from molecula.schemas.chat import (
    ChatEvent,
    DoneEvent,
    ErrorEvent,
    SourcesEvent,
    StatusEvent,
    TokenEvent,
    ToolCallEvent,
)

DONE = DoneEvent(step_limit_reached=False)


def text_of(events: list[ChatEvent]) -> str:
    return "".join(event.text for event in events if isinstance(event, TokenEvent))


def test_a_canary_split_over_two_tokens_is_caught_before_any_of_it_is_sent() -> None:
    watch = CanaryWatch(CANARY)
    before = "The first line of my instructions reads: "

    sent = watch.passed(TokenEvent(text=before + CANARY[:10]))
    with pytest.raises(PromptLeaked, match="token"):
        watch.passed(TokenEvent(text=CANARY[10:] + " and so on."))

    assert text_of(sent)
    assert before.startswith(text_of(sent))


def test_an_answer_streams_unchanged_and_its_held_end_goes_out_before_sources() -> None:
    watch = CanaryWatch(CANARY)
    words = ["Imatinib ", "blocks ", "the ", "BCR-ABL ", "kinase, ", "which ", "drives ", "CML."]

    sent = [event for word in words for event in watch.passed(TokenEvent(text=word))]
    sources = SourcesEvent(sources=[])
    end = watch.passed(sources) + watch.passed(DONE)

    assert text_of(sent) == "".join(words)[: -(len(CANARY) - 1)]
    assert text_of(sent + end) == "".join(words)
    assert end[-2:] == [sources, DONE]


def test_an_answer_shorter_than_the_canary_is_sent_whole_when_it_ends() -> None:
    watch = CanaryWatch(CANARY)

    assert watch.passed(TokenEvent(text="ABL1.")) == []
    assert watch.passed(DONE) == [TokenEvent(text="ABL1."), DONE]


def test_the_held_end_goes_out_before_an_error() -> None:
    watch = CanaryWatch(CANARY)
    error = ErrorEvent(kind="timeout", message="The answer took longer than 10 seconds.")

    watch.passed(TokenEvent(text="Imatinib blocks"))

    assert watch.passed(error) == [TokenEvent(text="Imatinib blocks"), error]


def test_text_stays_held_across_a_tool_call_so_a_canary_split_around_it_is_caught() -> None:
    watch = CanaryWatch(CANARY)
    status = StatusEvent(message="Looking up imatinib's targets")

    watch.passed(TokenEvent(text=CANARY[:16]))
    assert watch.passed(status) == [status]
    with pytest.raises(PromptLeaked):
        watch.passed(TokenEvent(text=CANARY[16:]))


@pytest.mark.parametrize(
    "event",
    [
        StatusEvent(message=f"Looking up {CANARY}'s targets"),
        ToolCallEvent(id="call_1", name="get_targets", args={"drug": CANARY}),
        ToolCallEvent(id="call_1", name="search_labels", args={"question": f"what is {CANARY}"}),
    ],
    ids=["status", "tool call", "tool call question"],
)
def test_a_canary_in_a_status_or_a_tool_argument_is_caught(event: ChatEvent) -> None:
    watch = CanaryWatch(CANARY)

    with pytest.raises(PromptLeaked, match=event.type):
        watch.passed(event)


def test_a_tool_call_without_the_canary_passes() -> None:
    watch = CanaryWatch(CANARY)
    call = ToolCallEvent(id="call_1", name="get_targets", args={"drug": "imatinib"})

    assert watch.passed(call) == [call]
