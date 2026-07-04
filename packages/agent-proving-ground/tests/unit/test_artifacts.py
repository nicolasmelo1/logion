from __future__ import annotations

import pytest

from logion_agent_proving_ground.artifacts import ArtifactStore


def test_artifact_store_rejects_path_traversal(tmp_path) -> None:
    store = ArtifactStore(tmp_path)
    with pytest.raises(ValueError, match="path traversal"):
        store.write_text("../escape.txt", "secret")
