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
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

# --- consent levels --------------------------------------------------------

OFF = "off"
LOCAL_ONLY = "local-only"
PROMPT = "prompt"
AUTO = "auto"

CONSENT_LEVELS: frozenset[str] = frozenset({OFF, LOCAL_ONLY, PROMPT, AUTO})

# --- envelope version ------------------------------------------------------

INTEGRATION_VERSION = "logion.observation.v1"

# --- forbidden payload keys (defence in depth) -----------------------------
# These must never appear in a serialised envelope.  The redaction check
# rejects any field whose name matches one of these substrings so a
# future caller cannot accidentally leak raw task data.

_FORBIDDEN_KEY_SUBSTRINGS: tuple[str, ...] = (
    "prompt",
    "source_code",
    "source",
    "code",
    "path",
    "tool_arg",
    "argument",
    "secret",
    "token",
    "key",
    "password",
    "credential",
    "model_context",
    "context",
    "terminal",
    "stdout",
    "stderr",
    "output",
    "request",
    "response",
    "body",
    "payload",
    "raw",
    "task_data",
    "task_input",
    "task_output",
    "content",
)

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

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe dict for spool emission."""
        return {k: v for k, v in asdict(self).items() if v is not None}

    def to_jsonl(self) -> str:
        """Return a single JSONL line (no trailing newline)."""
        return json.dumps(
            self.to_dict(), sort_keys=True, separators=(",", ":")
        )


_ALLOWED_FIELD_NAMES = frozenset(f.name for f in fields(ObservationEnvelope))


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


def _is_forbidden_key(key: str) -> bool:
    """True if *key* matches a forbidden payload substring."""
    lower = key.lower()
    return any(sub in lower for sub in _FORBIDDEN_KEY_SUBSTRINGS)


def assert_no_secrets(payload: dict[str, Any]) -> None:
    """Defensive check: reject envelopes carrying forbidden fields.

    Raises :class:`ValueError` if any key is outside the allowed
    envelope field set.  Allowed fields are the sanctioned envelope
    fields defined on :class:`ObservationEnvelope`; they are trusted by
    construction.  Unknown keys are rejected outright.  This is a
    guardrail against future callers accidentally leaking raw task data
    by adding ad-hoc fields to the payload.
    """
    for key in payload:
        if key not in _ALLOWED_FIELD_NAMES:
            raise ValueError(
                f"observation envelope field {key!r} is not permitted"
                f" — forbidden raw-task-data field"
            )


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
    if not should_spool(consent):
        return None
    payload = envelope.to_dict()
    assert_no_secrets(payload)
    spool_dir = observations_dir(logion_home)
    spool_dir.mkdir(parents=True, exist_ok=True)
    spool_path = spool_dir / "observations.jsonl"
    with spool_path.open("a", encoding="utf-8") as fh:
        fh.write(envelope.to_jsonl() + "\n")
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
