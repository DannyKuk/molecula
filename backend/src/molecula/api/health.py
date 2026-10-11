from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class HealthResponse(BaseModel):
    status: Literal["ok"]


@router.get("/health")
def health() -> HealthResponse:
    return HealthResponse(status="ok")
