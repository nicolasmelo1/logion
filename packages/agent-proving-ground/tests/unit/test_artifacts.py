from __future__ import annotations

from pathlib import Path

import pytest

from logion_agent_proving_ground.artifacts import (
    ArtifactStore,
    resolve_artifact_path,
)


def test_artifact_store_rejects_path_traversal(tmp_path) -> None:
    store = ArtifactStore(tmp_path)
    with pytest.raises(ValueError, match="path traversal"):
        store.write_text("../escape.txt", "secret")


def test_artifact_store_rejects_absolute_path(tmp_path) -> None:
    store = ArtifactStore(tmp_path)
    with pytest.raises(ValueError, match="path traversal"):
        store.write_text("/tmp/escape.txt", "secret")


def test_resolve_artifact_path_rejects_absolute_path(tmp_path) -> None:
    with pytest.raises(ValueError, match="path traversal"):
        resolve_artifact_path(tmp_path, str(Path("/tmp/escape.txt")))
