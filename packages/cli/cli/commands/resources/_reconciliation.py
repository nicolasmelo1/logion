# SPDX-License-Identifier: MIT
"""Reconciliation and ambiguity logic for resource inventory."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def content_digest(skill_dir: Path) -> str:
    """Compute SHA-256 over all non-marker files in *skill_dir*."""
    digest = hashlib.sha256()
    markers = {
        ".logion-lock.json",
        ".logion-manifest.json",
        ".logion-sig.json",
    }
    for path in sorted(skill_dir.rglob("*")):
        if not path.is_file() or path.name in markers:
            continue
        relative = path.relative_to(skill_dir).as_posix().encode()
        digest.update(relative + b"\0" + path.read_bytes() + b"\0")
    return digest.hexdigest()


def read_marker(path: Path) -> dict[str, Any] | None:
    """Read and validate a JSON marker file."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def reconciliation_status(skill_dir: Path) -> dict[str, str]:
    """Validate local evidence before assigning a reconciliation status."""
    digest = content_digest(skill_dir)
    status = "unlinked"
    evidence = "none"
    lock = read_marker(skill_dir / ".logion-lock.json")
    manifest = read_marker(skill_dir / ".logion-manifest.json")
    signature = read_marker(skill_dir / ".logion-sig.json")
    if (
        lock
        and all(
            isinstance(lock.get(key), str) and lock[key]
            for key in ("resource_version_id", "native_receipt_digest")
        )
        and lock.get("content_digest") == digest
    ):
        status, evidence = "exact", "validated-native-receipt"
    elif (
        manifest
        and all(
            isinstance(manifest.get(key), str) and manifest[key]
            for key in ("canonical_uri", "source_revision")
        )
        and manifest.get("content_digest") == digest
    ):
        status, evidence = "canonical", "validated-canonical-source"
    elif (
        signature
        and all(
            isinstance(signature.get(key), str) and signature[key]
            for key in ("algorithm", "key_id", "signature")
        )
        and signature.get("content_digest") == digest
    ):
        status = "signature-present-unverified"
        evidence = "structurally-valid-signature"
    return {"status": status, "content_digest": digest, "evidence": evidence}


def mark_ambiguities(results: list[dict[str, Any]]) -> None:
    """Mark resources that share a name across different scopes."""
    by_name: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        by_name.setdefault(str(result["name"]), []).append(result)
    for entries in by_name.values():
        if len(entries) < 2:
            continue
        for entry in entries:
            entry["ambiguous_name"] = True
            reconciliation = entry["reconciliation"]
            if reconciliation["status"] == "unlinked":
                reconciliation["status"] = "ambiguous"


def discover_native_state(  # noqa: C901 - manager schemas differ
    scope_root: Path, source: str = "all"
) -> list[dict[str, Any]]:
    """Read native manager state without modifying files or reinstalling."""
    results: list[dict[str, Any]] = []
    if source in {"all", "skills"}:
        lock = scope_root / "skills-lock.json"
        if lock.is_file():
            try:
                data = json.loads(lock.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
            entries = data.get("skills") if isinstance(data, dict) else []
            if isinstance(entries, dict):
                entries = list(entries.values())
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        results.append({
                            "manager": "skills",
                            "source": str(
                                entry.get("source")
                                or entry.get("locator")
                                or ""
                            ),
                            "revision": str(
                                entry.get("revision")
                                or entry.get("commit")
                                or ""
                            ),
                            "resource_version_id": entry.get(
                                "resource_version_id"
                            ),
                            "path": entry.get("path")
                            or entry.get("directory"),
                        })
    if source in {"all", "plugins"}:
        for path in (
            scope_root / ".agents/plugins/manifest.json",
            scope_root / ".claude/plugins.json",
            scope_root / "plugins.json",
        ):
            if not path.is_file():
                continue
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            entries = (
                data.get("plugins", data) if isinstance(data, dict) else data
            )
            if isinstance(entries, dict):
                entries = list(entries.values())
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        results.append({
                            "manager": "plugins",
                            "source": str(
                                entry.get("source")
                                or entry.get("locator")
                                or entry.get("repository")
                                or ""
                            ),
                            "revision": str(
                                entry.get("revision")
                                or entry.get("commit")
                                or ""
                            ),
                            "resource_version_id": entry.get(
                                "resource_version_id"
                            ),
                            "path": entry.get("path"),
                        })
    if source in {"all", "hf"}:
        refs = scope_root / ".cache/huggingface/hub"
        if refs.is_dir():
            for ref in sorted(refs.glob("models--*/refs/*")):
                try:
                    revision = ref.read_text(encoding="utf-8").strip()
                except OSError:
                    continue
                results.append({
                    "manager": "hf",
                    "source": ref.parent.parent.name.replace(
                        "models--", ""
                    ).replace("--", "/"),
                    "revision": revision,
                    "resource_version_id": None,
                    "path": str(ref.parent.parent),
                })
    return results
