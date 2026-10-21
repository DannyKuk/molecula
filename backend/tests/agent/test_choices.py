import asyncio

from choice_fakes import DEFAULT_MODEL, model_choices
from molecula.agent.choices import ModelChoices
from molecula.schemas.chat import ChatModel, ChecksChoice


def listed(choices: ModelChoices[str]) -> list[tuple[str, bool]]:
    return [(model.name, model.local) for model in asyncio.run(choices.models())]


def picked(
    choices: ModelChoices[str], name: str | None, checks: ChecksChoice = "tested"
) -> tuple[ChatModel, str] | None:
    return asyncio.run(choices.chat(name, checks))


def test_the_default_comes_first_then_the_local_then_the_cloud_models() -> None:
    choices = model_choices("default chat", local=["qwen/qwen3.8-27b"], cloud=["openai/gpt-6"])

    assert listed(choices) == [
        ("fake-model", True),
        ("qwen/qwen3.8-27b", True),
        ("openai/gpt-6", False),
    ]


def test_a_model_the_local_server_and_openrouter_share_is_listed_once_as_local() -> None:
    choices = model_choices(
        "default chat", local=["openai/gpt-oss-120b"], cloud=["openai/gpt-oss-120b"]
    )

    assert listed(choices) == [("fake-model", True), ("openai/gpt-oss-120b", True)]


def test_the_default_model_is_listed_once_when_the_local_server_lists_it_too() -> None:
    choices = model_choices("default chat", local=["fake-model", "google/gemma-4-31b"])

    assert listed(choices) == [("fake-model", True), ("google/gemma-4-31b", True)]


def test_no_name_or_the_defaults_name_answers_in_the_default_chat_whatever_the_checks() -> None:
    choices = model_choices("default chat", local=["google/gemma-4-31b"])

    assert picked(choices, None) == (DEFAULT_MODEL, "default chat")
    assert picked(choices, "fake-model") == (DEFAULT_MODEL, "default chat")
    assert picked(choices, None, "picked") == (DEFAULT_MODEL, "default chat")
    assert picked(choices, "fake-model", "picked") == (DEFAULT_MODEL, "default chat")


def test_a_name_no_model_has_finds_no_chat() -> None:
    choices = model_choices("default chat", local=["google/gemma-4-31b"], cloud=["openai/gpt-6"])

    assert picked(choices, "evil/model") is None


def test_a_picked_model_gets_its_own_chat_per_choice_of_checks_built_once() -> None:
    built: list[tuple[ChatModel, ChecksChoice]] = []

    def build(model: ChatModel, checks: ChecksChoice) -> str:
        built.append((model, checks))
        return f"chat with {model.name} and the {checks} checks"

    choices = model_choices("default chat", cloud=["openai/gpt-6"], build=build)
    gpt6 = ChatModel(name="openai/gpt-6", local=False)

    assert picked(choices, "openai/gpt-6") == (gpt6, "chat with openai/gpt-6 and the tested checks")
    assert picked(choices, "openai/gpt-6", "picked") == (
        gpt6,
        "chat with openai/gpt-6 and the picked checks",
    )
    assert picked(choices, "openai/gpt-6", "tested")
    assert picked(choices, "openai/gpt-6", "picked")
    assert built == [(gpt6, "tested"), (gpt6, "picked")]


def test_the_local_list_is_read_again_so_a_new_download_shows_up() -> None:
    lists = [["google/gemma-4-31b"], ["google/gemma-4-31b", "qwen/qwen3.8-27b"]]

    async def local_names() -> list[str]:
        return lists.pop(0)

    choices = ModelChoices(
        DEFAULT_MODEL,
        "default chat",
        cloud=[],
        local_names=local_names,
        build=lambda model, checks: model.name,
    )

    assert len(listed(choices)) == 2
    assert picked(choices, "qwen/qwen3.8-27b") is not None
