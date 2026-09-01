"""Local credential store for a runner node.

The store persists two secrets in one ``runner.json`` file inside the
state directory, written with mode ``0600``:

- the runner key issued by the coordinator (``logion_runner_...``),
  which authenticates lease/heartbeat/artifact/receipt calls;
- the Ed25519 signing private key the runner embeds in every receipt
  signature, returned at enrollment as ``signing_key_pem``.

Rotating rewrites the same file with the coordinator's new material;
the previous key stays valid only until the coordinator retires it.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

STORE_FILENAME = "runner.json"
RUNNER_KEY_PREFIX = "logion_runner_"


class KeyStoreError(RuntimeError):
    """The local runner credential store is unusable."""


@dataclass(frozen=True)
class EnrollSecrets:
    """The coordinator's enrollment response, verified before storing."""

    runner_id: str
    runner_key: str
    signing_key_pem: str
    key_fingerprint: str
    signing_key_fingerprint: str


def load_enroll_secrets(payload: dict) -> EnrollSecrets:
    """Narrow an enrollment/rotation response body into secrets."""
    missing = [
        key
        for key in (
            "runner_id",
            "runner_key",
            "signing_key_pem",
            "key_fingerprint",
            "signing_key_fingerprint",
        )
        if not isinstance(payload.get(key), str) or not payload[key]
    ]
    if missing:
        raise KeyStoreError(
            f"coordinator response is missing fields: {', '.join(missing)}"
        )
    runner_key = payload["runner_key"]
    if not runner_key.startswith(RUNNER_KEY_PREFIX):
        raise KeyStoreError(
            "runner key does not start with the required prefix"
        )
    try:
        serialization.load_pem_private_key(
            payload["signing_key_pem"].encode(), password=None
        )
    except (ValueError, TypeError) as exc:
        raise KeyStoreError(f"signing key is not valid PEM: {exc}") from exc
    return EnrollSecrets(
        runner_id=payload["runner_id"],
        runner_key=runner_key,
        signing_key_pem=payload["signing_key_pem"],
        key_fingerprint=payload["key_fingerprint"],
        signing_key_fingerprint=payload["signing_key_fingerprint"],
    )


def key_fingerprint(value: str | bytes) -> str:
    """Return the first 16 hex digits of the SHA-256 of *value*."""
    raw = value.encode() if isinstance(value, str) else value
    return hashlib.sha256(raw).hexdigest()[:16]


class KeyStore:
    """Read/write the ``runner.json`` credential file."""

    def __init__(self, state_dir: Path) -> None:
        self._path = Path(state_dir) / STORE_FILENAME

    @property
    def path(self) -> Path:
        return self._path

    def exists(self) -> bool:
        return self._path.is_file()

    def load_secrets(self) -> EnrollSecrets:
        """Return the verified enrollment secrets from disk."""
        payload = self._read_raw()
        return load_enroll_secrets(payload)

    def runner_key(self) -> str:
        """Return the stored runner key (bearer credential)."""
        return self.load_secrets().runner_key

    def signing_key(self) -> Ed25519PrivateKey:
        """Return the stored Ed25519 private key."""
        secrets = self.load_secrets()
        key = serialization.load_pem_private_key(
            secrets.signing_key_pem.encode(), password=None
        )
        if not isinstance(key, Ed25519PrivateKey):
            raise KeyStoreError("stored signing key is not Ed25519")
        return key

    def signing_public_key(self) -> Ed25519PublicKey:
        return self.signing_key().public_key()

    def fingerprints(self) -> dict[str, str]:
        """Compute both fingerprints and compare with the stored ones."""
        secrets = self.load_secrets()
        return {
            "key_fingerprint": key_fingerprint(secrets.runner_key),
            "signing_key_fingerprint": key_fingerprint(
                secrets.signing_key_pem
            ),
            "stored_key_fingerprint": secrets.key_fingerprint,
            "stored_signing_key_fingerprint": (
                secrets.signing_key_fingerprint
            ),
        }

    def save(self, secrets: EnrollSecrets) -> None:
        """Persist secrets atomically with mode 0600, creating the dir."""
        load_enroll_secrets(secrets.__dict__)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.parent.chmod(0o700)
        payload = {
            "runner_id": secrets.runner_id,
            "runner_key": secrets.runner_key,
            "signing_key_pem": secrets.signing_key_pem,
            "key_fingerprint": secrets.key_fingerprint,
            "signing_key_fingerprint": secrets.signing_key_fingerprint,
        }
        fd, tmp_name = tempfile.mkstemp(
            dir=self._path.parent, prefix=".runner-", suffix=".tmp"
        )
        try:
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(payload, fh, indent=2, sort_keys=True)
                fh.write("\n")
            os.replace(tmp_name, self._path)
        except BaseException:
            with contextlib.suppress(OSError):
                os.unlink(tmp_name)
            raise
        self._verify_mode()

    def _read_raw(self) -> dict:
        if not self._path.is_file():
            raise KeyStoreError(f"no runner credential file at {self._path}")
        self._verify_mode()
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise KeyStoreError(
                f"runner credential file unreadable: {exc}"
            ) from exc
        if not isinstance(payload, dict):
            raise KeyStoreError("runner credential file is not an object")
        return payload

    def _verify_mode(self) -> None:
        mode = stat.S_IMODE(self._path.stat().st_mode)
        if mode & 0o077:
            raise KeyStoreError(
                f"runner credential file {self._path} has mode "
                f"{oct(mode)}; expected 0600"
            )
