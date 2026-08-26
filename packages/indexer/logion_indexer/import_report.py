# SPDX-License-Identifier: MIT
"""The auditable record of what one crawl imported and what it refused.

A crawl that prints "create: 3" tells an operator how many rows it
would write. It cannot tell them what the source offered, what was
dropped, or why -- so a source that silently stopped publishing half
its catalog reads exactly like a source that never had those entries.

The report closes that gap: ``seen`` is what the source offered,
``created``/``matched`` is what survived, and ``quarantined`` plus
``errors_by_code`` is what did not and under which stable code. The
codes are contract, not log text: an operator groups by them across
runs, so renaming one changes what every saved report means.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from ._json import JsonObject


@dataclass(frozen=True)
class QuarantinedRecord:
    """One input the crawl refused, named and coded."""

    identifier: str
    error_code: str
    reason: str

    def to_dict(self) -> JsonObject:
        return {
            "identifier": self.identifier,
            "error_code": self.error_code,
            "reason": self.reason,
        }


@dataclass
class ImportReport:
    """Counters and quarantine for a single crawl of a single source."""

    source: str
    adapter: str
    seen: int = 0
    created: int = 0
    matched: int = 0
    new_versions: int = 0
    cursor: str | None = None
    duration_ms: int = 0
    partial: bool = False
    quarantine: list[QuarantinedRecord] = field(default_factory=list)

    @property
    def quarantined(self) -> int:
        return len(self.quarantine)

    @property
    def errors_by_code(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in self.quarantine:
            counts[record.error_code] = counts.get(record.error_code, 0) + 1
        return counts

    def to_dict(self) -> JsonObject:
        """Serialize in the shape the phase gate and operators read.

        ``quarantined`` and ``errors_by_code`` are written out rather
        than left derivable: a saved report is read by things that never
        see this class, and a reader that has to recount the quarantine
        list to learn the count will eventually disagree with one that
        does not.
        """
        return {
            "source": self.source,
            "adapter": self.adapter,
            "cursor": self.cursor,
            "seen": self.seen,
            "created": self.created,
            "matched": self.matched,
            "new_versions": self.new_versions,
            "quarantined": self.quarantined,
            "errors_by_code": self.errors_by_code,
            "quarantine": [record.to_dict() for record in self.quarantine],
            "duration_ms": self.duration_ms,
            "partial": self.partial,
            "status": self.status,
        }

    @property
    def status(self) -> str:
        """Whether the crawl finished the source it was pointed at.

        ``partial`` means an adapter failed mid-run, so absent entries
        prove nothing. Quarantine alone is still ``completed``: refusing
        a malformed entry is the crawl working, not failing.
        """
        return "partial" if self.partial else "completed"

    def write(self, path: str | Path) -> None:
        Path(path).write_text(
            json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8"
        )

    def summary_lines(self) -> list[str]:
        """Human-readable counters, in the order an operator scans them."""
        lines = [
            f"import report: {self.adapter} <- {self.source}",
            f"  seen: {self.seen}",
            f"  created: {self.created}",
            f"  matched: {self.matched}",
            f"  new_versions: {self.new_versions}",
            f"  quarantined: {self.quarantined}",
        ]
        lines.extend(
            f"    {code}: {count}"
            for code, count in sorted(self.errors_by_code.items())
        )
        return lines


__all__ = ["ImportReport", "QuarantinedRecord"]
