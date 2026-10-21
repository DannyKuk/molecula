import asyncio
from collections.abc import Awaitable, Callable, Sequence

from molecula.schemas.chat import ChatModel, Checker, CheckerId


class ModelChoices[Chat]:
    """The models a user may pick to write the answers (#37), the checkers that may check the
    messages (#363), and the chat each pair answers in, built the first time it is picked.

    The default comes first, then the models the local server lists, then the cloud models. The
    local list is read again each time, so a model downloaded in LM Studio shows up without a
    restart. A name the local server and OpenRouter share is the local model. Chats are built
    one at a time, so two requests that pick the same pair at once share one chat.
    """

    def __init__(
        self,
        default: ChatModel,
        default_chat: Chat,
        *,
        cloud: Sequence[ChatModel],
        local_names: Callable[[], Awaitable[list[str]]],
        checkers: Sequence[Checker],
        default_checker: CheckerId,
        build: Callable[[ChatModel, CheckerId], Awaitable[Chat]],
    ) -> None:
        self.default = default
        self.checkers = list(checkers)
        self.default_checker = default_checker
        self._chats: dict[tuple[ChatModel, CheckerId], Chat] = {
            (default, default_checker): default_chat
        }
        self._cloud = cloud
        self._local_names = local_names
        self._build = build
        self._building = asyncio.Lock()

    async def models(self) -> list[ChatModel]:
        local = [ChatModel(name=name, local=True) for name in await self._local_names()]
        by_name: dict[str, ChatModel] = {}
        for model in [self.default, *local, *self._cloud]:
            by_name.setdefault(model.name, model)
        return list(by_name.values())

    def offers(self, checker: CheckerId) -> bool:
        return checker == "answer" or any(offered.id == checker for offered in self.checkers)

    async def chat(
        self, name: str | None, checker: CheckerId | None = None
    ) -> tuple[ChatModel, Chat] | None:
        """The model named `name`, the default without a name, and its chat with `checker`, the
        default checker without one; None when no model has that name. The checker must be one
        `offers` accepts."""
        model = self.default
        if name is not None and name != self.default.name:
            found = next((model for model in await self.models() if model.name == name), None)
            if found is None:
                return None
            model = found
        key = (model, checker or self.default_checker)
        async with self._building:
            if key not in self._chats:
                self._chats[key] = await self._build(*key)
        return model, self._chats[key]
