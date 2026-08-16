# SPDX-License-Identifier: MIT
"""Local acquisition receipts for resource inventory (schema_version 1).

Receipts live under ``$LOGION_HOME/inventory/`` keyed by installation id and
record what was acquired, through which channel, with which verification
level, and where it landed. Receipts are local-only: they never contain user
identity, tokens, or repository contents, and are never uploaded.
"""

from __future__ import annotations

import contextlib
import datetime
import hashlib
import json
import os
import re
import tempfile
from pathlib import Path

from cli import _local_state
from cli._json import JsonObject, child

RECEIPT_SCHEMA_VERSION = 1


def _canonical_json_dumps(data: JsonObject) -> bytes:
    """RFC 8785 (JCS) canonical serialization for receipt digests."""
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def native_receipt_digest(native_evidence: JsonObject) -> str:
    """Recompute the digest over canonical native evidence bytes.

    Fails closed on unserializable evidence rather than minting a receipt
    the verifier cannot re-check.
    """
    payload = _canonical_json_dumps(native_evidence)
    return hashlib.sha256(payload).hexdigest()


def aggregate_content_digest(components: list[JsonObject]) -> str:
    """Recompute the hosted-bundle digest using the API canonical format."""
    content_hash_input = ""
    for component in components:
        aggregate_key = component.get("aggregate_key")
        if not isinstance(aggregate_key, str) or not aggregate_key:
            raise ValueError("aggregate component lacks aggregate_key")
        component_digest = component.get("digest") or ""
        content_hash_input += (
            f"{aggregate_key}:{component.get('size_bytes')}"
            f":{component_digest};"
        )
    digest = hashlib.sha256(content_hash_input.encode("utf-8")).hexdigest()
    return "sha256:" + digest


def native_manager_tag(native_evidence: JsonObject) -> str:
    """Build the ``<manager_name>@<manager_version>`` identity string."""
    name = str(native_evidence.get("manager_name") or "")
    version = str(native_evidence.get("manager_version") or "")
    return f"{name}@{version}" if name and version else name or "unknown"


def _inventory_dir() -> Path:
    root = _local_state.get_home() / "inventory"
    root.mkdir(parents=True, exist_ok=True)
    return root


def scope_id_for_target(scope_kind: str, scope_root: Path) -> str:
    """Domain-separated HMAC-style opaque id for a scope target.

    A plain SHA-256 of a repository path is forbidden by the phase
    contract; the HMAC key is the local home so ids are profile/node
    scoped and stable without leaking the absolute path.
    """
    import hmac

    key = str(_local_state.get_home()).encode("utf-8")
    message = f"logion.scope.v1\0{scope_kind}\0{scope_root}".encode()
    return hmac.new(key, message, "sha256").hexdigest()


def installation_id_for(scope_id: str, relative_target_path: str) -> str:
    """Opaque id for one installation within a scope."""
    import hmac

    key = str(_local_state.get_home()).encode("utf-8")
    message = (
        f"logion.installation.v1\0{scope_id}\0{relative_target_path}".encode()
    )
    return hmac.new(key, message, "sha256").hexdigest()


def save_receipt(receipt: JsonObject) -> Path:
    """Persist a receipt atomically under ``$LOGION_HOME/inventory/``."""
    _validate_receipt(receipt)
    installation_id = receipt["installation_id"]
    if not re.fullmatch(r"[0-9a-f]{64}", installation_id):
        raise ValueError("installation_id must be an opaque hex id")
    path = _inventory_dir() / f"{installation_id}.json"
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name, suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(
                json.dumps(receipt, indent=2, ensure_ascii=False) + "\n"
            )
        os.replace(tmp_name, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_name)
        raise
    return path


def load_receipts() -> list[JsonObject]:
    """Load all local receipts, skipping unreadable/corrupt files."""
    root = _local_state.get_home() / "inventory"
    if not root.is_dir():
        return []
    receipts: list[JsonObject] = []
    for path in sorted(root.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(payload, dict) and payload.get("schema_version") == 1:
            receipts.append(payload)
    return receipts


def find_receipt(
    *, scope_kind: str, scope_root: Path, relative_target_path: str
) -> JsonObject | None:
    """Look up the receipt for one installation identity, if recorded."""
    installation_id = installation_id_for(
        scope_id_for_target(scope_kind, scope_root), relative_target_path
    )
    for receipt in load_receipts():
        if receipt.get("installation_id") == installation_id:
            return receipt
    return None


def _validate_receipt(receipt: JsonObject) -> None:
    required = (
        "schema_version",
        "resource_id",
        "version_id",
        "distribution_id",
        "resource_type",
        "content_digest",
        "channel",
        "harness",
        "scope_kind",
        "scope_id",
        "installation_id",
        "target_path",
        "relative_target_path",
        "acquired_at",
        "verification",
    )
    missing = [key for key in required if key not in receipt]
    if missing:
        raise ValueError(f"receipt missing keys: {missing}")
    evidence = child(receipt, "native_evidence")
    if evidence is not None:
        digest = native_receipt_digest(evidence)
        if receipt.get("native_receipt_digest") != digest:
            raise ValueError(
                "native_receipt_digest mismatch: refusing to persist"
            )
        if receipt.get("verification") == "exact":
            if evidence.get("content_digest") != receipt.get("content_digest"):
                raise ValueError("exact receipt content digest mismatch")
            components = evidence.get("aggregate_components")
            if not isinstance(components, list) or not components:
                raise ValueError(
                    "exact receipt lacks aggregate digest components"
                )
            computed = aggregate_content_digest(components)
            if computed != receipt.get("content_digest"):
                raise ValueError("exact receipt aggregate digest mismatch")


def now_rfc3339() -> str:
    return (
        datetime.datetime.now(datetime.UTC).isoformat().replace("+00:00", "Z")
    )
