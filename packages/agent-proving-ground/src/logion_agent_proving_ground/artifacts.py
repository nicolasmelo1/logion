from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from logion_agent_proving_ground.redaction import redact_json, redact_text


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
        value: Any,
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
        if ".." in Path(relative).parts:
            raise ValueError(f"path traversal rejected: {relative}")
        return self.root / relative

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
        value: Any,  # noqa: ARG002
        *,
        redact: bool = True,  # noqa: ARG002
    ) -> Path:
        return Path()

    async def flush(self) -> None:
        pass


def _json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(
        f"Object of type {type(value).__name__} is not JSON serializable"
    )
