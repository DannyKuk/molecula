from collections.abc import Awaitable, Callable, Sequence

from molecula.schemas.chat import ChatModel, ChecksChoice


class ModelChoices[Chat]:
    """The models a user may pick to write the answers (#37), and the chat each one answers in
    with each choice of checks (#363), built the first time it is picked.

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
        build: Callable[[ChatModel, ChecksChoice], Chat],
    ) -> None:
        self.default = default
        self._default_chat = default_chat
        self._chats: dict[tuple[ChatModel, ChecksChoice], Chat] = {}
        self._cloud = cloud
        self._local_names = local_names
        self._build = build

    async def models(self) -> list[ChatModel]:
        local = [ChatModel(name=name, local=True) for name in await self._local_names()]
        by_name: dict[str, ChatModel] = {}
        for model in [self.default, *local, *self._cloud]:
            by_name.setdefault(model.name, model)
        return list(by_name.values())

    async def chat(
        self, name: str | None, checks: ChecksChoice = "tested"
    ) -> tuple[ChatModel, Chat] | None:
        """The model named `name` and its chat with `checks`, the default's without a name;
        None when no model has that name. The default model answers in its own chat whatever
        `checks` says."""
        if name is None or name == self.default.name:
            return self.default, self._default_chat
        model = next((model for model in await self.models() if model.name == name), None)
        if model is None:
            return None
        if (model, checks) not in self._chats:
            self._chats[model, checks] = self._build(model, checks)
        return model, self._chats[model, checks]
