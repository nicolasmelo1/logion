from __future__ import annotations

import json
from pathlib import Path

from agent_proving_ground.redaction import redact_json, redact_text


class ArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def mkdir(self, relative: str) -> Path:
        path = self._resolve(relative)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_text(
        self,
        relative: str,
        value: str,
        *,
        redact: bool = True,
    ) -> Path:
        path = self._resolve(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        text = redact_text(value) if redact else value
        path.write_text(text, encoding="utf-8")
        return path

    def write_json(
        self,
        relative: str,
        value: object,
        *,
        redact: bool = True,
    ) -> Path:
        path = self._resolve(relative)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = redact_json(value) if redact else value
        path.write_text(
            json.dumps(data, indent=2, default=_json_default),
            encoding="utf-8",
        )
        return path

    def _resolve(self, relative: str) -> Path:
        return resolve_artifact_path(self.root, relative)

    async def flush(self) -> None:
        pass


class NullArtifactStore:
    def mkdir(self, relative: str) -> Path:  # noqa: ARG002
        return Path()

    def write_text(
        self,
        relative: str,  # noqa: ARG002
        value: str,  # noqa: ARG002
        *,
        redact: bool = True,  # noqa: ARG002
    ) -> Path:
        return Path()

    def write_json(
        self,
        relative: str,  # noqa: ARG002
        value: object,  # noqa: ARG002
        *,
        redact: bool = True,  # noqa: ARG002
    ) -> Path:
        return Path()

    async def flush(self) -> None:
        pass


def _json_default(value: object) -> str:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(
        f"Object of type {type(value).__name__} is not JSON serializable"
    )


def resolve_artifact_path(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"path traversal rejected: {relative}")
    return root / candidate
