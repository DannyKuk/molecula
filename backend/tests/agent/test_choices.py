import asyncio

from choice_fakes import DEFAULT_MODEL, GPT_OSS, model_choices
from molecula.agent.choices import ModelChoices
from molecula.schemas.chat import ChatModel, CheckerId


def listed(choices: ModelChoices[str]) -> list[tuple[str, bool]]:
    return [(model.name, model.local) for model in asyncio.run(choices.models())]


def picked(
    choices: ModelChoices[str], name: str | None, checker: CheckerId | None = None
) -> tuple[ChatModel, str] | None:
    return asyncio.run(choices.chat(name, checker))


async def no_local_models() -> list[str]:
    return []


def built_chats(choices_built: list[tuple[ChatModel, CheckerId]]) -> ModelChoices[str]:
    def build(model: ChatModel, checker: CheckerId) -> str:
        choices_built.append((model, checker))
        return f"{model.name} checked by {checker}"

    return model_choices("default chat", cloud=["openai/gpt-6"], build=build)


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


def test_the_default_model_and_checker_answer_in_the_default_chat() -> None:
    choices = model_choices("default chat", local=["google/gemma-4-31b"])

    assert picked(choices, None) == (DEFAULT_MODEL, "default chat")
    assert picked(choices, "fake-model") == (DEFAULT_MODEL, "default chat")
    assert picked(choices, "fake-model", "decision") == (DEFAULT_MODEL, "default chat")


def test_a_name_no_model_has_finds_no_chat() -> None:
    choices = model_choices("default chat", local=["google/gemma-4-31b"], cloud=["openai/gpt-6"])

    assert picked(choices, "evil/model") is None


def test_each_model_and_checker_gets_its_own_chat_built_once() -> None:
    built: list[tuple[ChatModel, CheckerId]] = []
    choices = built_chats(built)
    gpt6 = ChatModel(name="openai/gpt-6", local=False)

    assert picked(choices, "openai/gpt-6") == (gpt6, "openai/gpt-6 checked by decision")
    assert picked(choices, "openai/gpt-6", "answer") == (gpt6, "openai/gpt-6 checked by answer")
    assert picked(choices, "openai/gpt-6", "decision")
    assert picked(choices, "openai/gpt-6", "answer")
    assert built == [(gpt6, "decision"), (gpt6, "answer")]


def test_the_default_model_with_another_checker_gets_its_own_chat() -> None:
    built: list[tuple[ChatModel, CheckerId]] = []
    choices = built_chats(built)

    assert picked(choices, None, "answer") == (DEFAULT_MODEL, "fake-model checked by answer")
    assert picked(choices, None, "local") == (DEFAULT_MODEL, "fake-model checked by local")
    assert built == [(DEFAULT_MODEL, "answer"), (DEFAULT_MODEL, "local")]


def test_the_answering_model_is_always_offered_and_only_the_listed_checkers_besides() -> None:
    offline = model_choices("default chat", checkers=[GPT_OSS], default_checker="local")

    assert offline.offers("answer")
    assert offline.offers("local")
    assert not offline.offers("decision")


def test_two_requests_that_pick_the_same_model_at_once_share_one_chat() -> None:
    built: list[ChatModel] = []

    async def build(model: ChatModel, checker: CheckerId) -> str:
        built.append(model)
        await asyncio.sleep(0)
        return f"chat {len(built)}"

    choices = ModelChoices(
        DEFAULT_MODEL,
        "default chat",
        cloud=[ChatModel(name="openai/gpt-6", local=False)],
        local_names=no_local_models,
        checkers=[GPT_OSS],
        default_checker="local",
        build=build,
    )

    async def pick_twice() -> list[tuple[ChatModel, str] | None]:
        return await asyncio.gather(choices.chat("openai/gpt-6"), choices.chat("openai/gpt-6"))

    first, second = asyncio.run(pick_twice())

    assert first == second
    assert len(built) == 1


def test_the_local_list_is_read_again_so_a_new_download_shows_up() -> None:
    lists = [["google/gemma-4-31b"], ["google/gemma-4-31b", "qwen/qwen3.8-27b"]]

    async def local_names() -> list[str]:
        return lists.pop(0)

    async def build(model: ChatModel, checker: CheckerId) -> str:
        return model.name

    choices = ModelChoices(
        DEFAULT_MODEL,
        "default chat",
        cloud=[],
        local_names=local_names,
        checkers=[GPT_OSS],
        default_checker="local",
        build=build,
    )

    assert len(listed(choices)) == 2
    assert picked(choices, "qwen/qwen3.8-27b") is not None
