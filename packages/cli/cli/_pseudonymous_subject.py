# SPDX-License-Identifier: MIT
"""Local signer-capable pseudonymous subject for no-account reporting.

The subject is a locally held Ed25519 keypair whose public key hashes to a
stable opaque identifier. Anonymous receipts/feedback sign the exact request
claims so the server can prove the subject is real, stable, and locally held —
not a random opaque id the client typed.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from cli._json import JsonObject, JsonValue
from cli._local_state import _atomic_write_text, get_home

SCHEMA_VERSION = 1
ALGORITHM = "ed25519"
_SUBJECT_FILENAME = "pseudonymous_subject.json"


@dataclass(frozen=True)
class PseudonymousSubject:
    subject_id: str
    public_key: str
    _private_key: str

    def sign_claims(self, operation: str, claims: JsonObject) -> str:
        payload = _canonical_payload(operation, claims)
        signature = _private_key(self._private_key).sign(payload)
        return _b64(signature)


def subject_path(home: Path | None = None) -> Path:
    return (home or get_home()) / _SUBJECT_FILENAME


def ensure_subject(home: Path | None = None) -> PseudonymousSubject:
    path = subject_path(home)
    loaded = _load(path)
    if loaded is not None:
        return loaded
    subject = _generate_subject()
    _persist(path, subject)
    return subject


def build_receipt_proof(
    claims: JsonObject,
    home: Path | None = None,
) -> JsonObject:
    subject = ensure_subject(home)
    return {
        "pseudonymous_public_key": subject.public_key,
        "pseudonymous_signature": subject.sign_claims("usage_receipt", claims),
    }


def build_feedback_proof(
    claims: JsonObject, home: Path | None = None
) -> JsonObject:
    subject = ensure_subject(home)
    return {
        "pseudonymous_public_key": subject.public_key,
        "pseudonymous_signature": subject.sign_claims(
            "resource_feedback", claims
        ),
    }


def normalize_claims(claims: JsonObject) -> JsonObject:
    return {
        key: _normalize_value(value)
        for key, value in sorted(claims.items())
        if value is not None
    }


def _canonical_payload(operation: str, claims: JsonObject) -> bytes:
    normalized: JsonObject = {
        "schema_version": SCHEMA_VERSION,
        "algorithm": ALGORITHM,
        "operation": operation,
        "claims": normalize_claims(claims),
    }
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _normalize_value(
    value: JsonValue | Decimal | UUID | datetime,
) -> JsonValue:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return format(value.normalize(), "f")
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [_normalize_value(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _normalize_value(v) for k, v in sorted(value.items())}
    msg = f"unsupported pseudonymous claim value: {type(value).__name__}"
    raise TypeError(msg)


def _load(path: Path) -> PseudonymousSubject | None:
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    subject_id = raw.get("subject_id")
    public_key = raw.get("public_key")
    private_key = raw.get("private_key")
    algorithm = raw.get("algorithm")
    if not all(
        isinstance(v, str) and v for v in (subject_id, public_key, private_key)
    ):
        return None
    if algorithm != ALGORITHM:
        return None
    return PseudonymousSubject(
        subject_id=str(subject_id),
        public_key=str(public_key),
        _private_key=str(private_key),
    )


def _generate_subject() -> PseudonymousSubject:
    private_key = Ed25519PrivateKey.generate()
    public_key_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    private_key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    return PseudonymousSubject(
        subject_id=hashlib.sha256(public_key_bytes).hexdigest(),
        public_key=_b64(public_key_bytes),
        _private_key=_b64(private_key_bytes),
    )


def _persist(path: Path, subject: PseudonymousSubject) -> None:
    payload = {
        "schema_version": SCHEMA_VERSION,
        "algorithm": ALGORITHM,
        "subject_id": subject.subject_id,
        "public_key": subject.public_key,
        "private_key": subject._private_key,
    }
    _atomic_write_text(
        path,
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
    )
    with contextlib.suppress(OSError):
        path.chmod(0o600)


def _private_key(value: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(_unb64(value))


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _unb64(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)
