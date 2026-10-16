"""A stand-in for `huggingface_hub.snapshot_download` that writes a tiny model into the cache
layout instead of downloading one, and records how it was called."""

import hashlib
from pathlib import Path
from typing import Any

import pytest

from molecula.rag import embeddings

FAKE_WEIGHTS = b"fake weights"


class FakeHub:
    def __init__(self, weights: bytes) -> None:
        self.weights = weights
        self.calls: list[dict[str, Any]] = []

    def snapshot_download(self, repo_id: str, **options: Any) -> str:
        self.calls.append({"repo_id": repo_id, **options})
        repo_folder = "models--" + repo_id.replace("/", "--")
        snapshot = Path(options["cache_dir"]) / repo_folder / "snapshots" / options["revision"]
        for name in options["allow_patterns"]:
            path = snapshot / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(self.weights if name == embeddings.WEIGHTS_FILE else b"{}")
        return str(snapshot)


def install_fake_hub(monkeypatch: pytest.MonkeyPatch, weights: bytes = FAKE_WEIGHTS) -> FakeHub:
    """Replace the hub download with a fake and pin the fake weights' hash, so the pinned check
    passes for `weights == FAKE_WEIGHTS`."""
    hub = FakeHub(weights)
    monkeypatch.setattr("huggingface_hub.snapshot_download", hub.snapshot_download)
    monkeypatch.setattr(embeddings, "WEIGHTS_SHA256", hashlib.sha256(FAKE_WEIGHTS).hexdigest())
    return hub
