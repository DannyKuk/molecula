from fastapi import APIRouter, HTTPException

from molecula.api.dependencies import LabelUpdateButtonDep
from molecula.schemas.stats import LabelUpdateStatus

router = APIRouter()


@router.post("/labels/update", status_code=202)
def start_label_update(updater: LabelUpdateButtonDep) -> LabelUpdateStatus:
    """Start a label update and return at once; GET /stats shows when it ends. 409 while a run
    is going, 503 when the backend can't update (OFFLINE=1, or no store built)."""
    if not updater.can_run:
        raise HTTPException(status_code=503, detail=updater.off_reason)
    if not updater.start():
        raise HTTPException(status_code=409, detail="A label update is already running.")
    return updater.status()
