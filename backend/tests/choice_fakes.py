"""Model choices for tests: a default model, the models a fake local server lists and the cloud
models, each answering in the chat `build` makes for it and the choice of checks."""

from collections.abc import Callable, Sequence

from molecula.agent.choices import ModelChoices
from molecula.schemas.chat import ChatModel, ChecksChoice

DEFAULT_MODEL = ChatModel(name="fake-model", local=True)


def model_choices[Chat](
    default_chat: Chat,
    *,
    local: Sequence[str] = (),
    cloud: Sequence[str] = (),
    build: Callable[[ChatModel, ChecksChoice], Chat] | None = None,
) -> ModelChoices[Chat]:
    async def local_names() -> list[str]:
        return list(local)

    return ModelChoices(
        DEFAULT_MODEL,
        default_chat,
        cloud=[ChatModel(name=name, local=False) for name in cloud],
        local_names=local_names,
        build=build or (lambda model, checks: default_chat),
    )
