"""Model choices for tests: a default model, the models a fake local server lists and the cloud
models, and the checkers, each pair answering in the chat `build` makes for it."""

from collections.abc import Callable, Sequence

from molecula.agent.choices import ModelChoices
from molecula.schemas.chat import ChatModel, Checker, CheckerId

DEFAULT_MODEL = ChatModel(name="fake-model", local=True)
JEV = Checker(id="decision", name="jev-1.13", local=False)
GPT_OSS = Checker(id="local", name="openai/gpt-oss-20b", local=True)


def model_choices[Chat](
    default_chat: Chat,
    *,
    local: Sequence[str] = (),
    cloud: Sequence[str] = (),
    checkers: Sequence[Checker] = (JEV, GPT_OSS),
    default_checker: CheckerId = "decision",
    build: Callable[[ChatModel, CheckerId], Chat] | None = None,
) -> ModelChoices[Chat]:
    async def local_names() -> list[str]:
        return list(local)

    return ModelChoices(
        DEFAULT_MODEL,
        default_chat,
        cloud=[ChatModel(name=name, local=False) for name in cloud],
        local_names=local_names,
        checkers=checkers,
        default_checker=default_checker,
        build=build or (lambda model, checker: default_chat),
    )
