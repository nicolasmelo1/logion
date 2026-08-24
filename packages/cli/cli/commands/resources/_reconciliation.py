# SPDX-License-Identifier: MIT
"""Reconciliation and ambiguity logic for resource inventory."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cli._json import JsonObject, child

from ._dsh_reconciliation import discover_dsh_state


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


def read_marker(path: Path) -> JsonObject | None:
    """Read and validate a JSON marker file."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def receipt_status(
    receipt: JsonObject, scope_root: Path | None
) -> tuple[str, str]:
    """Re-verify a local acquisition receipt against bytes on disk.

    A receipt is a claim, not proof. When it carries per-file digests they
    are recomputed here, so an installation that was deleted or edited
    after acquisition reports ``drifted`` instead of inheriting the
    verification level it had at install time.
    """
    evidence = child(receipt, "native_evidence")
    file_digests = child(evidence, "file_digests")
    claimed = str(receipt.get("verification") or "unverified")
    if scope_root is None or not file_digests:
        # Channels that delegate to a native manager record no per-file
        # digests; the receipt is reported without upgrading its trust.
        return claimed, "unrechecked-local-receipt"
    for relative, expected in sorted(file_digests.items()):
        candidate = scope_root / str(relative)
        if not candidate.is_file():
            return "drifted", f"missing-file:{relative}"
        actual = hashlib.sha256(candidate.read_bytes()).hexdigest()
        if actual != expected:
            return "drifted", f"digest-mismatch:{relative}"
    return claimed, "validated-local-receipt"


def reconciliation_status(
    skill_dir: Path,
    receipt: JsonObject | None = None,
    scope_root: Path | None = None,
) -> dict[str, str]:
    """Validate local evidence before assigning a reconciliation status."""
    digest = content_digest(skill_dir)
    if receipt is not None:
        status, evidence = receipt_status(receipt, scope_root)
        return {
            "status": status,
            "content_digest": digest,
            "evidence": evidence,
        }
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


def mark_ambiguities(results: list[JsonObject]) -> None:
    """Mark resources that share a name across different scopes."""
    by_name: dict[str, list[JsonObject]] = {}
    for result in results:
        by_name.setdefault(str(result["name"]), []).append(result)
    for entries in by_name.values():
        if len(entries) < 2:
            continue
        for entry in entries:
            entry["ambiguous_name"] = True
            reconciliation = child(entry, "reconciliation")
            if reconciliation["status"] == "unlinked":
                reconciliation["status"] = "ambiguous"


def discover_native_state(  # noqa: C901 - manager schemas differ
    scope_root: Path, source: str = "all"
) -> list[JsonObject]:
    """Read native manager state without modifying files or reinstalling."""
    results: list[JsonObject] = []
    if source in {"all", "dsh"}:
        results.extend(discover_dsh_state(scope_root))
    if source in {"all", "skills"}:
        lock = scope_root / "skills-lock.json"
        if lock.is_file():
            from ._channels._skills_lock import (
                UnsupportedLockfileError,
                parse_skills_lock,
            )

            try:
                entries = parse_skills_lock(lock)
            except UnsupportedLockfileError as exc:
                # Fail closed: an unreadable or unknown lockfile shape is
                # reported, never guessed at.
                results.append({
                    "manager": "skills",
                    "source": "",
                    "revision": "",
                    "resource_version_id": None,
                    "path": str(lock),
                    "unsupported": str(exc),
                })
                entries = []
            results.extend(
                {
                    "manager": "skills",
                    "name": entry.name,
                    "source": entry.source,
                    "revision": entry.revision,
                    "content_digest": entry.content_digest,
                    "resource_version_id": None,
                    "installed_paths": list(entry.installed_paths),
                    "path": entry.installed_paths[0]
                    if entry.installed_paths
                    else None,
                }
                for entry in entries
            )
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
