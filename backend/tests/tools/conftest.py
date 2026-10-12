import pytest

from tool_fakes import (
    FakeCompoundService,
    FakeFilterExtractor,
    FakeLabelRetriever,
    FakeTargetService,
)


@pytest.fixture
def compounds() -> FakeCompoundService:
    return FakeCompoundService()


@pytest.fixture
def targets() -> FakeTargetService:
    return FakeTargetService()


@pytest.fixture
def extractor() -> FakeFilterExtractor:
    return FakeFilterExtractor()


@pytest.fixture
def retriever() -> FakeLabelRetriever:
    return FakeLabelRetriever()
