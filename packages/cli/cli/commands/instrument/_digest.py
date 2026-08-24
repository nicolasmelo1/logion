# SPDX-License-Identifier: MIT
"""Digest computation for instrument projections.

- ``distribution_digest``: SHA-256 over the canonical serialization of the
  portable core (the publisher's artifact), proving byte-identity.
- ``profile_digest``: SHA-256 over the canonical serialization of the
  instrumentation profile (sorted keys, no insignificant whitespace),
  matching ``logion_instrumentation.validator.canonical_digest``.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from cli._json import JsonObject, JsonValue

#: Prefix for all digest strings.
_DIGEST_PREFIX = "sha256:"


def _sha256_hex(data: bytes) -> str:
    """Return ``sha256:<hex>`` for *data*."""
    return f"{_DIGEST_PREFIX}{hashlib.sha256(data).hexdigest()}"


def file_digest(path: Path) -> str:
    """Compute the SHA-256 digest of a file's raw bytes."""
    return _sha256_hex(path.read_bytes())


def directory_digest(root: Path) -> str:
    """Compute a deterministic digest over all files in *root*.

    Files are visited in sorted order; each contributes its relative
    path and content hash to a combined hash. This is the
    ``distribution_digest`` — proof that the portable core is
    byte-identical inside the projection.
    """
    h = hashlib.sha256()
    for file_path in sorted(root.rglob("*")):
        if file_path.is_file():
            relative = file_path.relative_to(root).as_posix()
            file_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
            h.update(f"{relative}\0{file_hash}\n".encode())
    return f"{_DIGEST_PREFIX}{h.hexdigest()}"


def canonical_json(obj: JsonValue) -> str:
    """Serialize *obj* with sorted keys and no insignificant whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def profile_digest(profile: JsonObject) -> str:
    """Compute the canonical SHA-256 digest of an instrumentation profile.

    This matches ``logion_instrumentation.validator.canonical_digest``
    so a reporter's digest and the generator's digest are the same
    value for the same profile.
    """
    payload = canonical_json(profile).encode("utf-8")
    return _sha256_hex(payload)


def verify_byte_identical(
    source: Path,
    destination: Path,
) -> bool:
    """Return True if *destination* is byte-identical to *source*.

    Used to prove the portable core was copied, not rewritten.
    """
    if not source.exists() or not destination.exists():
        return False
    return file_digest(source) == file_digest(destination)
