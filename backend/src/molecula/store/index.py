import shutil
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings as ChromaSettings

from molecula.schemas.labels import ProductType, SectionGroup

COLLECTION = "label_chunks"
MODEL_KEY = "embedding_model"


class IndexModelMismatch(Exception):
    """The index was built with another embedding model than the settings name."""


@dataclass(frozen=True)
class Chunk:
    """A piece of one label section, with what retrieval filters on and the source to cite."""

    id: str
    text: str
    cid: int
    substance: str
    brand: str | None
    product_type: ProductType
    section: str
    section_group: SectionGroup
    sensitive: bool
    set_id: str
    effective_time: str
    url: str


class LabelIndex:
    """The ChromaDB collection of label chunks and their embeddings, rebuilt from scratch."""

    def __init__(self, path: Path) -> None:
        self._client = chromadb.PersistentClient(
            path=str(path), settings=ChromaSettings(anonymized_telemetry=False)
        )

    @classmethod
    def empty(cls, path: Path) -> LabelIndex:
        """A new index in an emptied folder. Chroma keeps a deleted collection's files and its
        SQLite file only grows, so a rebuild in place grew the index from 74.8 to 96.7 MB."""
        if path.exists():
            try:
                shutil.rmtree(path)
            except PermissionError as error:
                raise PermissionError(
                    f"Can't empty {path}: another process has the index open. "
                    "Stop the backend, then rebuild."
                ) from error
        return cls(path)

    def rebuild(
        self, chunks: Sequence[Chunk], vectors: Sequence[Sequence[float]], model: str
    ) -> None:
        """Replace the whole collection with `chunks`, embedded by `model` as `vectors` (same
        order)."""
        if len(chunks) != len(vectors):
            raise ValueError(f"{len(chunks)} chunks but {len(vectors)} vectors")
        if self._exists():
            self._client.delete_collection(COLLECTION)
        # embedding_function=None: vectors always come from our model, and Chroma's default
        # would download an ONNX model.
        collection = self._client.create_collection(
            COLLECTION,
            configuration={"hnsw": {"space": "cosine"}},
            metadata={MODEL_KEY: model},
            embedding_function=None,
        )
        batch = self._client.get_max_batch_size()
        for start in range(0, len(chunks), batch):
            part = chunks[start : start + batch]
            collection.add(
                ids=[chunk.id for chunk in part],
                documents=[chunk.text for chunk in part],
                metadatas=[to_metadata(chunk) for chunk in part],
                embeddings=[list(vector) for vector in vectors[start : start + batch]],
            )

    def model(self) -> str | None:
        """The embedding model the index was built with; None before the first build."""
        if not self._exists():
            return None
        metadata = self._client.get_collection(COLLECTION, embedding_function=None).metadata
        return (metadata or {}).get(MODEL_KEY)

    def check_model(self, model: str) -> None:
        """Raise IndexModelMismatch unless the index was built with `model`. Vectors of two
        models don't compare: a query would fail on the dimension or quietly find nonsense."""
        built_with = self.model()
        if built_with != model:
            raise IndexModelMismatch(
                f"The index was built with {built_with}, but the settings name {model}. "
                "Rebuild it with `python -m molecula.ingest index`."
            )

    def chunks(self) -> list[Chunk]:
        """Every stored chunk, ordered by ID; empty before the first build."""
        if not self._exists():
            return []
        collection = self._client.get_collection(COLLECTION, embedding_function=None)
        stored = collection.get(include=["documents", "metadatas"])
        documents = stored["documents"] or []
        metadatas = stored["metadatas"] or []
        rows = zip(stored["ids"], documents, metadatas, strict=True)
        return sorted(
            (Chunk(id=id_, text=text, **from_metadata(metadata)) for id_, text, metadata in rows),
            key=lambda chunk: chunk.id,
        )

    def search(
        self, vector: Sequence[float], n: int, where: dict[str, Any] | None = None
    ) -> list[tuple[Chunk, float]]:
        """Up to `n` chunks closest to `vector` that match the ChromaDB `where` filter, best
        first, with their cosine similarity; empty before the first build."""
        if not self._exists():
            return []
        collection = self._client.get_collection(COLLECTION, embedding_function=None)
        found = collection.query(
            query_embeddings=[list(vector)],
            n_results=n,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        rows = zip(
            found["ids"][0],
            (found["documents"] or [[]])[0],
            (found["metadatas"] or [[]])[0],
            (found["distances"] or [[]])[0],
            strict=True,
        )
        return [
            (Chunk(id=id_, text=text, **from_metadata(metadata)), 1.0 - distance)
            for id_, text, metadata, distance in rows
        ]

    def _exists(self) -> bool:
        return COLLECTION in {collection.name for collection in self._client.list_collections()}


def to_metadata(chunk: Chunk) -> dict[str, Any]:
    # ChromaDB metadata values can't be None, so a label without a brand leaves the key out.
    fields = asdict(chunk)
    del fields["id"], fields["text"]
    return {key: value for key, value in fields.items() if value is not None}


def from_metadata(metadata: Any) -> dict[str, Any]:
    return {"brand": None, **metadata}
