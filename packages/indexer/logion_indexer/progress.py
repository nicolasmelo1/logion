"""Bounded aggregate progress receipts for indexer runs."""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime

from .pusher import RunStats
from .transport import Transport


@dataclass
class RunProgress:
    """Emit local JSONL and best-effort persisted aggregate checkpoints."""

    transport: Transport
    base_url: str
    run_id: str
    stats: RunStats
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    adapter_counts: dict[str, int] = field(default_factory=dict)
    adapter_errors: dict[str, str] = field(default_factory=dict)

    def checkpoint(self, stage: str, *, status: str = "running") -> None:
        now = datetime.now(UTC)
        snapshot = {
            "status": status,
            "stage": stage,
            "discovered": self.stats.discovered,
            "resolved": self.stats.resolved,
            "deduped": self.stats.deduped,
            "created": self.stats.created,
            "updated": self.stats.updated,
            "skipped": self.stats.skipped,
            "errors": self.stats.errors,
            "partial": self.stats.partial,
            "adapter_counts": dict(sorted(self.adapter_counts.items())),
            "adapter_errors": dict(sorted(self.adapter_errors.items())),
            "started_at": self.started_at.isoformat(),
            "updated_at": now.isoformat(),
        }
        sys.stderr.write(
            "indexer-progress " + json.dumps(snapshot, sort_keys=True) + "\n"
        )
        sys.stderr.flush()
        try:
            response = self.transport.patch(
                f"{self.base_url.rstrip('/')}/v1/admin/indexing/runs/{self.run_id}/progress",
                json_body=snapshot,
            )
            if response.status not in (200, 201, 204):
                self._publish_error(f"HTTP {response.status}")
        except Exception as exc:  # Progress must not hide pipeline failure.
            self._publish_error(f"{type(exc).__name__}: {exc}")

    @staticmethod
    def _publish_error(message: str) -> None:
        sys.stderr.write(f"indexer-progress publish-error: {message}\n")
        sys.stderr.flush()

    def adapter(
        self, name: str, discovered: int, error: str | None = None
    ) -> None:
        self.adapter_counts[name] = discovered
        if error:
            self.adapter_errors[name] = error.replace("\r", " ").replace(
                "\n", " "
            )[:500]
