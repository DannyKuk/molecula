from typing import Annotated

from fastapi import APIRouter, Query

from molecula.api.dependencies import KnowledgeBaseDep, LabelUpdaterDep, UsageLogDep
from molecula.schemas.stats import Stats

router = APIRouter()


@router.get("/stats")
def stats(
    knowledge_base: KnowledgeBaseDep,
    label_updater: LabelUpdaterDep,
    usage_log: UsageLogDep,
    days: Annotated[int, Query(ge=1, le=365)] = 30,
) -> Stats:
    """What the store holds, the label update, and how the chat was used over the last `days`
    UTC days."""
    return Stats(
        knowledge_base=knowledge_base.stats(),
        label_update=label_updater.status(),
        usage=usage_log.stats(days),
    )
