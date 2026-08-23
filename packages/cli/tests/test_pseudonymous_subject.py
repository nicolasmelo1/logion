# SPDX-License-Identifier: MIT
"""Tests for the local signer-capable pseudonymous subject."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cli._json import JsonObject
from cli._pseudonymous_subject import (
    build_feedback_proof,
    build_receipt_proof,
    ensure_subject,
    subject_path,
)


def test_subject_is_persisted_and_reused(tmp_path: Path) -> None:
    first = ensure_subject(tmp_path)
    second = ensure_subject(tmp_path)

    assert first.subject_id == second.subject_id
    assert first.public_key == second.public_key
    assert subject_path(tmp_path).is_file()


def test_distinct_claims_produce_distinct_signatures(tmp_path: Path) -> None:
    first = build_receipt_proof({"observation_id": "obs-1"}, home=tmp_path)
    second = build_receipt_proof({"observation_id": "obs-2"}, home=tmp_path)

    assert (
        first["pseudonymous_public_key"] == second["pseudonymous_public_key"]
    )
    assert first["pseudonymous_signature"] != second["pseudonymous_signature"]


def test_feedback_and_receipt_use_separate_domains(tmp_path: Path) -> None:
    claims: JsonObject = {"resource_id": "res-1", "version_id": "ver-1"}

    feedback = build_feedback_proof(claims, home=tmp_path)
    receipt = build_receipt_proof(claims, home=tmp_path)

    assert (
        feedback["pseudonymous_public_key"]
        == receipt["pseudonymous_public_key"]
    )
    assert (
        feedback["pseudonymous_signature"] != receipt["pseudonymous_signature"]
    )


def test_subject_file_is_private_json(tmp_path: Path) -> None:
    subject = ensure_subject(tmp_path)
    path = subject_path(tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["subject_id"] == subject.subject_id
    assert payload["public_key"] == subject.public_key
    assert payload["algorithm"] == "ed25519"
    # The private key file must never be group/world readable.
    assert path.stat().st_mode & 0o077 == 0


def test_temporary_file_is_created_private(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The tmp file used for the atomic rename must also be 0o600.

    ``_persist`` opens the temporary file with ``os.open(..., 0o600)`` before
    writing any bytes, so there is no window where the key is world-readable
    even on the intermediate path.
    """

    import cli._pseudonymous_subject as module

    open_modes: list[int] = []
    real_open = module.os.open

    def _spy_open(path, flags, mode=0o777, *args, **kwargs):
        open_modes.append(mode)
        return real_open(path, flags, mode, *args, **kwargs)

    monkeypatch.setattr(module.os, "open", _spy_open)
    ensure_subject(tmp_path)

    assert open_modes, "os.open was never called"
    # Every open used to persist the subject must be 0o600.
    assert all(mode & 0o077 == 0 for mode in open_modes)
