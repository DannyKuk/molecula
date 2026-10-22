from fastapi import APIRouter

from molecula.api.dependencies import EmbeddingSetupDep
from molecula.schemas.retrieval import EmbeddingSetup

router = APIRouter()


@router.get("/retrieval")
def retrieval(setup: EmbeddingSetupDep) -> EmbeddingSetup:
    """The embedding model and section bonus this instance searches the labels with, so the
    benchmark page describes the setup it runs: bge-m3 with +0.15 locally, a cloud model with no
    bonus (#96, #350). Answers also when the chat is off."""
    return setup
