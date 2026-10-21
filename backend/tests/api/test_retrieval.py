from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from molecula.api import dependencies
from molecula.main import app
from molecula.schemas.retrieval import EmbeddingSetup


@pytest.fixture
def serve() -> Iterator[None]:
    yield
    app.dependency_overrides.clear()


@pytest.mark.parametrize(
    "setup",
    [
        EmbeddingSetup(embedding_model="BAAI/bge-m3", local=True, section_group_boost=0.15),
        EmbeddingSetup(
            embedding_model="google/gemini-embedding-2", local=False, section_group_boost=0.0
        ),
    ],
)
@pytest.mark.usefixtures("serve")
def test_retrieval_reports_the_instance_setup(setup: EmbeddingSetup) -> None:
    app.dependency_overrides[dependencies.embedding_setup] = lambda: setup

    response = TestClient(app).get("/retrieval")

    assert response.status_code == 200
    assert response.json() == setup.model_dump()
