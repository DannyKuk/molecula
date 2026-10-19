import asyncio
import logging

from langchain_core.language_models import BaseChatModel

from molecula.agent.decisions import DecisionModelError
from molecula.rag.filters import Decider, DecisionFilterExtractor, FilterExtractor
from molecula.schemas.retrieval import LabelFilter
from molecula.services.compounds import CompoundService
from molecula.services.labels import LabelService

logger = logging.getLogger(__name__)


class DecisionFirstFilterExtractor(FilterExtractor):
    """Extracts the label filter with the decision model, and with the chat model when the
    decision model fails, so a search never fails because of its filter (#290)."""

    def __init__(
        self,
        model: BaseChatModel,
        decision_model: Decider,
        compounds: CompoundService,
        labels: LabelService,
    ) -> None:
        super().__init__(model, compounds, labels)
        self._decisions = DecisionFilterExtractor(decision_model, compounds, labels)

    def extract(self, question: str) -> LabelFilter:
        try:
            # `search_labels` is a sync tool, which LangChain runs in a worker thread without an
            # event loop, so the decision model's async call is run to its end here.
            return asyncio.run(self._decisions.extract(question))
        except DecisionModelError as error:
            logger.warning("The chat model extracts the label filter: %r", error)
            return super().extract(question)
