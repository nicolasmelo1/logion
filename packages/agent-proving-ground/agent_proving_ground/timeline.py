from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path


class Timeline:
    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self._path.open("a", encoding="utf-8")

    def event(self, type_: str, **fields: object) -> None:
        line = json.dumps(
            {
                "type": type_,
                "timestamp": _utc_now(),
                **fields,
            },
            default=_json_default,
        )
        self._file.write(line + "\n")
        self._file.flush()

    def close(self) -> None:
        self._file.close()

    async def flush(self) -> None:
        self._file.flush()


class NullTimeline:
    def event(self, type_: str, **fields: object) -> None:
        pass

    def close(self) -> None:
        pass

    async def flush(self) -> None:
        pass


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _json_default(value: object) -> str:
    if isinstance(value, Path):
        return str(value)
    raise TypeError(
        f"Object of type {type(value).__name__} is not JSON serializable"
    )
