from typing import Annotated

from fastapi import Depends, Request

from molecula.services.compounds import CompoundService


def compound_service(request: Request) -> CompoundService:
    """The app's one compound service, built at startup. Tests replace it with an override."""
    return request.app.state.compound_service


CompoundServiceDep = Annotated[CompoundService, Depends(compound_service)]
