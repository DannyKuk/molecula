from langchain_core.messages import AIMessage, HumanMessage

from molecula.schemas.usage import Usage, usage_of

CALL = Usage(input_tokens=100, output_tokens=20, total_tokens=120, cost_usd=0.0003)


def test_calls_add_up() -> None:
    total = CALL + CALL

    assert total == Usage(input_tokens=200, output_tokens=40, total_tokens=240, cost_usd=0.0006)


def test_no_calls_use_nothing() -> None:
    assert Usage() + CALL == CALL


def test_a_call_without_usage_makes_the_sum_unknown() -> None:
    assert CALL + Usage.unreported() == Usage.unreported()


def test_a_call_without_a_cost_makes_only_the_cost_unknown() -> None:
    total = CALL + CALL.model_copy(update={"cost_usd": None})

    assert (total.total_tokens, total.cost_usd) == (240, None)


def test_a_message_gives_its_tokens_and_cost() -> None:
    message = AIMessage(
        content="Aspirin is an NSAID.",
        usage_metadata={"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
        response_metadata={"token_usage": {"prompt_tokens": 100, "cost": 0.0003}},
    )

    assert usage_of(message) == CALL


def test_a_message_without_usage_is_unknown_not_zero() -> None:
    assert usage_of(AIMessage(content="Aspirin is an NSAID.")) == Usage.unreported()
    assert usage_of(HumanMessage("What is aspirin?")) == Usage.unreported()
