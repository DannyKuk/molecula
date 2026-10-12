import pytest

from tool_fakes import FakeCompoundService, FakeTargetService


@pytest.fixture
def compounds() -> FakeCompoundService:
    return FakeCompoundService()


@pytest.fixture
def targets() -> FakeTargetService:
    return FakeTargetService()
