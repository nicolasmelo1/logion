# SPDX-License-Identifier: MIT
"""ARD connectors source: fetch and pin the upstream agent-finders.json.

This is an indexer **control-plane source**. It fetches the upstream
``ards-project/ard-connectors`` directory's ``agent-finders.json`` by
an immutable GitHub commit, validates the shape, stores provenance,
and provides sync/diff/approve/status operations.

CRITICAL: No connector files or finder preferences are installed into
customer clients. This module runs server-side in the indexer only.
The ``selected`` field in the upstream directory is a connector-side
user preference and is always ignored by the indexer.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Literal

from logion_indexer._json import JsonObject, as_object, opt_str
from logion_indexer.transport import Transport

#: Default upstream repository for ard-connectors.
UPSTREAM_REPO = "ards-project/ard-connectors"

#: Default file path within the repository.
UPSTREAM_FILE = "agent-finders.json"

#: Default branch to fetch (pinned by commit in production).
UPSTREAM_BRANCH = "main"

#: GitHub raw content base URL.
GITHUB_RAW = "https://raw.githubusercontent.com"

#: GitHub API commits endpoint.
GITHUB_API = "https://api.github.com"

SnapshotStatus = Literal[
    "fresh", "stale", "rejected", "pending_operator_approval"
]


@dataclass(frozen=True)
class FinderEntry:
    """A single Agent Finder entry from agent-finders.json."""

    id: str
    name: str
    description: str = ""
    search: str = ""
    mcp: str = ""

    @classmethod
    def from_json(cls, obj: JsonObject) -> FinderEntry:
        return cls(
            id=opt_str(obj, "id", ""),
            name=opt_str(obj, "name", ""),
            description=opt_str(obj, "description", ""),
            search=opt_str(obj, "search", ""),
            mcp=opt_str(obj, "mcp", ""),
        )


@dataclass(frozen=True)
class AgentFindersSnapshot:
    """A pinned snapshot of the upstream agent-finders.json.

    Attributes:
        repo: Upstream repository (``owner/name``).
        commit_sha: Immutable commit SHA the file was fetched from.
        file_digest: SHA-256 of the fetched file content.
        fetched_at: Unix timestamp when the snapshot was fetched.
        finders: Tuple of finder entries.
        raw: The raw JSON content.
        validation_error: Error message if validation failed, else None.
    """

    repo: str
    commit_sha: str
    file_digest: str
    fetched_at: float
    finders: tuple[FinderEntry, ...]
    raw: str
    validation_error: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.validation_error is None

    @property
    def status(self) -> SnapshotStatus:
        if self.validation_error is not None:
            return "rejected"
        return "fresh"


@dataclass
class SnapshotDiff:
    """Diff between two snapshots.

    Attributes:
        added: Finder IDs present in the new snapshot but not the old.
        removed: Finder IDs present in the old snapshot but not the new.
        changed: Finder IDs whose content changed between snapshots.
        unchanged: Finder IDs whose content is identical.
    """

    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    changed: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed or self.changed)


@dataclass
class ARDConnectorsSource:
    """Fetch and manage pinned agent-finders.json snapshots.

    This is an indexer control-plane source. It does NOT install
    anything into customer clients, the Logion CLI, companion, or
    ``~/.agentfinder``.
    """

    transport: Transport
    repo: str = UPSTREAM_REPO
    file_path: str = UPSTREAM_FILE

    def fetch_snapshot(
        self,
        commit_sha: str | None = None,
    ) -> AgentFindersSnapshot:
        """Fetch a snapshot of agent-finders.json.

        Args:
            commit_sha: Specific commit to fetch. If None, fetches the
                latest commit on the default branch.
        """
        if commit_sha is None:
            commit_sha = self._fetch_latest_commit()

        url = f"{GITHUB_RAW}/{self.repo}/{commit_sha}/{self.file_path}"
        resp = self.transport.get(url)

        if resp.status != 200:
            return AgentFindersSnapshot(
                repo=self.repo,
                commit_sha=commit_sha,
                file_digest="",
                fetched_at=time.time(),
                finders=(),
                raw="",
                validation_error=(f"fetch failed: HTTP {resp.status}"),
            )

        raw = resp.body.decode("utf-8")
        file_digest = hashlib.sha256(resp.body).hexdigest()
        fetched_at = time.time()

        validation_error, finders = self._validate(raw)

        return AgentFindersSnapshot(
            repo=self.repo,
            commit_sha=commit_sha,
            file_digest=file_digest,
            fetched_at=fetched_at,
            finders=tuple(finders),
            raw=raw,
            validation_error=validation_error,
        )

    def diff_snapshots(
        self,
        old: AgentFindersSnapshot,
        new: AgentFindersSnapshot,
    ) -> SnapshotDiff:
        """Compute the diff between two snapshots."""
        old_finders = {f.id: f for f in old.finders}
        new_finders = {f.id: f for f in new.finders}

        old_ids = set(old_finders)
        new_ids = set(new_finders)

        added = sorted(new_ids - old_ids)
        removed = sorted(old_ids - new_ids)
        changed = sorted(
            fid
            for fid in old_ids & new_ids
            if _finder_content(old_finders[fid])
            != _finder_content(new_finders[fid])
        )
        unchanged = sorted(
            fid for fid in old_ids & new_ids if fid not in changed
        )

        return SnapshotDiff(
            added=added,
            removed=removed,
            changed=changed,
            unchanged=unchanged,
        )

    def _fetch_latest_commit(self) -> str:
        """Fetch the latest commit SHA from the default branch."""
        url = f"{GITHUB_API}/repos/{self.repo}/commits/{UPSTREAM_BRANCH}"
        resp = self.transport.get(url)
        if resp.status != 200:
            raise RuntimeError(
                f"failed to fetch latest commit: HTTP {resp.status}"
            )
        data = resp.json()
        if isinstance(data, dict):
            sha = data.get("sha")
            if isinstance(sha, str):
                return sha
        raise RuntimeError("could not parse commit SHA from response")

    @staticmethod
    def _validate(raw: str) -> tuple[str | None, list[FinderEntry]]:
        """Validate the agent-finders.json shape.

        Returns ``(error, finders)``. If validation fails, ``error``
        is a string and ``finders`` is empty.
        """
        try:
            doc = json.loads(raw)
        except json.JSONDecodeError as e:
            return (f"invalid JSON: {e}", [])

        obj = as_object(doc, where="agent-finders.json")

        # `selected` is a connector-side user preference — ignored.
        # We do not read it.

        finders_raw = obj.get("finders")
        if not isinstance(finders_raw, list):
            return ("missing or invalid 'finders' array", [])

        finders: list[FinderEntry] = []
        seen_ids: set[str] = set()
        for item in finders_raw:
            if not isinstance(item, dict):
                continue
            finder = FinderEntry.from_json(item)
            if not finder.id:
                continue
            if finder.id in seen_ids:
                return (
                    f"duplicate finder id: {finder.id!r}",
                    [],
                )
            seen_ids.add(finder.id)
            finders.append(finder)

        return (None, finders)


def _finder_content(f: FinderEntry) -> str:
    """Render a finder's content for diffing."""
    return f"{f.name}|{f.description}|{f.search}|{f.mcp}"


__all__ = [
    "ARDConnectorsSource",
    "AgentFindersSnapshot",
    "FinderEntry",
    "SnapshotDiff",
    "SnapshotStatus",
]
