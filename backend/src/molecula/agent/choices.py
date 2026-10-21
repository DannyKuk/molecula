from collections.abc import Awaitable, Callable, Sequence

from molecula.schemas.chat import ChatModel


class ModelChoices[Chat]:
    """The models a user may pick to write the answers (#37), and the chat each one answers in,
    built the first time it is picked.

    The default comes first, then the models the local server lists, then the cloud models. The
    local list is read again each time, so a model downloaded in LM Studio shows up without a
    restart. A name the local server and OpenRouter share is the local model.
    """

    def __init__(
        self,
        default: ChatModel,
        default_chat: Chat,
        *,
        cloud: Sequence[ChatModel],
        local_names: Callable[[], Awaitable[list[str]]],
        build: Callable[[ChatModel], Chat],
    ) -> None:
        self.default = default
        self._chats = {default: default_chat}
        self._cloud = cloud
        self._local_names = local_names
        self._build = build

    async def models(self) -> list[ChatModel]:
        local = [ChatModel(name=name, local=True) for name in await self._local_names()]
        by_name: dict[str, ChatModel] = {}
        for model in [self.default, *local, *self._cloud]:
            by_name.setdefault(model.name, model)
        return list(by_name.values())

    async def chat(self, name: str | None) -> tuple[ChatModel, Chat] | None:
        """The model named `name` and its chat, the default's without a name; None when no
        model has that name."""
        if name is None or name == self.default.name:
            return self.default, self._chats[self.default]
        model = next((model for model in await self.models() if model.name == name), None)
        if model is None:
            return None
        if model not in self._chats:
            self._chats[model] = self._build(model)
        return model, self._chats[model]
