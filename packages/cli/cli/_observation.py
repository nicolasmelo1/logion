# SPDX-License-Identifier: MIT
"""Versioned local observation envelope for harness resource use.

Plugins/extensions/hooks emit a versioned local envelope when an
installed resource is used by a harness.  The envelope is written to the
shared Logion local spool under ``$LOGION_HOME/observations/`` as JSONL.

The envelope deliberately carries **no** raw task data.  It must not
contain raw prompts, source code, paths, tool arguments, secrets, model
context, or arbitrary terminal output.  Only opaque-local identifiers
and outcome metadata are recorded.  An observation is not a rating; the
agent/user reviews the proposed payload before any feedback submission.

Consent levels:

- ``off`` — no spool and no network.
- ``local-only`` — local attribution/inventory only.
- ``prompt`` — queue a minimum-disclosure feedback proposal.
- ``auto`` — send only the separately documented narrow receipt class;
  ratings, prose reviews, and raw task data still require explicit
  policy/consent.
"""

from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from cli._observation_validation import (
    assert_allowed_payload_keys,
    validate_envelope_fields,
)

# --- consent levels --------------------------------------------------------

OFF = "off"
LOCAL_ONLY = "local-only"
PROMPT = "prompt"
AUTO = "auto"

CONSENT_LEVELS: frozenset[str] = frozenset({OFF, LOCAL_ONLY, PROMPT, AUTO})

# --- envelope version ------------------------------------------------------

INTEGRATION_VERSION = "logion.observation.v1"

# Fields permitted on the envelope — anything else is rejected.
# Populated after the dataclass is defined below.
_ALLOWED_FIELD_NAMES: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ObservationEnvelope:
    """Versioned local observation record for one resource-use event.

    All identifiers are opaque-local unless explicitly noted.  No field
    carries raw prompts, source code, paths, tool arguments, secrets,
    model context, or terminal output.
    """

    event: str  # e.g. "resource.use.completed"
    harness: str  # adapter name, e.g. "codex"
    harness_session_id: str  # opaque-local
    installation_id: str  # local-id
    resource_version_id: str | None  # "when-exact"
    scope_kind: str  # canonical scope, e.g. "repo-root"
    scope_id: str  # opaque-local
    task_class: str | None  # e.g. "software-development"
    outcome: str  # completed|failed|abandoned|unknown
    started_at: str  # RFC3339
    finished_at: str  # RFC3339
    integration_version: str  # e.g. INTEGRATION_VERSION

    def __post_init__(self) -> None:
        validate_envelope_fields(
            event=self.event,
            harness=self.harness,
            harness_session_id=self.harness_session_id,
            installation_id=self.installation_id,
            resource_version_id=self.resource_version_id,
            scope_kind=self.scope_kind,
            scope_id=self.scope_id,
            task_class=self.task_class,
            outcome=self.outcome,
            started_at=self.started_at,
            finished_at=self.finished_at,
            integration_version=self.integration_version,
            expected_version=INTEGRATION_VERSION,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dict for spool emission."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    def to_jsonl(self) -> str:
        """Return a single JSONL line (no trailing newline)."""
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":")
        )


_ALLOWED_FIELD_NAMES = frozenset({
    "event",
    "harness",
    "harness_session_id",
    "installation_id",
    "resource_version_id",
    "scope_kind",
    "scope_id",
    "task_class",
    "outcome",
    "started_at",
    "finished_at",
    "integration_version",
})


@dataclass(frozen=True)
class ConsentConfig:
    """Resolved consent configuration for observation emission."""

    level: str = OFF

    def __post_init__(self) -> None:
        if self.level not in CONSENT_LEVELS:
            raise ValueError(
                f"unknown consent level: {self.level!r} "
                f"(must be one of {sorted(CONSENT_LEVELS)})"
            )


def should_spool(consent: str) -> bool:
    """True if the given consent level permits local spool emission.

    ``off`` disables spooling entirely; ``local-only``, ``prompt``, and
    ``auto`` all permit writing the local envelope (network submission is
    gated separately by the feedback layer).
    """
    return consent in (LOCAL_ONLY, PROMPT, AUTO)


def assert_no_secrets(payload: dict[str, Any]) -> None:
    """Defensive check: reject envelopes carrying forbidden fields.

    Raises :class:`ValueError` if any key is outside the allowed
    envelope field set.  Allowed fields are the sanctioned envelope
    fields defined on :class:`ObservationEnvelope`; they are trusted by
    construction.  Unknown keys are rejected outright.  This is a
    guardrail against future callers accidentally leaking raw task data
    by adding ad-hoc fields to the payload.
    """
    assert_allowed_payload_keys(payload, _ALLOWED_FIELD_NAMES)


def observations_dir(logion_home: Path | None = None) -> Path:
    """Return the observations spool directory under LOGION_HOME."""
    if logion_home is None:
        env = os.environ.get("LOGION_HOME")
        home = Path(env) if env else Path.home() / ".logion"
    else:
        home = Path(logion_home)
    return home / "observations"


def spool_envelope(
    envelope: ObservationEnvelope,
    *,
    consent: str,
    logion_home: Path | None = None,
) -> Path | None:
    """Append *envelope* to the local JSONL spool if consent allows.

    Returns the spool file path if written, ``None`` if consent is
    ``off``.  Performs the no-secrets invariant before writing.
    """
    ConsentConfig(level=consent)
    if not should_spool(consent):
        return None
    payload = envelope.to_dict()
    assert_no_secrets(payload)
    spool_dir = observations_dir(logion_home)
    if spool_dir.is_symlink():
        raise ValueError("observation spool directory must not be a symlink")
    spool_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    spool_dir.chmod(0o700)
    spool_path = spool_dir / "observations.jsonl"
    if spool_path.is_symlink():
        raise ValueError("observation spool file must not be a symlink")
    flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
    flags |= getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(spool_path, flags, 0o600)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError("observation spool must be a regular file")
        os.chmod(spool_path, 0o600)
        os.write(fd, (envelope.to_jsonl() + "\n").encode())
    finally:
        os.close(fd)
    return spool_path


__all__ = [
    "AUTO",
    "CONSENT_LEVELS",
    "INTEGRATION_VERSION",
    "LOCAL_ONLY",
    "OFF",
    "PROMPT",
    "ConsentConfig",
    "ObservationEnvelope",
    "assert_no_secrets",
    "observations_dir",
    "should_spool",
    "spool_envelope",
]
