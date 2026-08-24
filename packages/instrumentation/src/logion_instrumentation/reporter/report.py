#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Python binding for the Logion consented-observation reporter.

Standard library only — no third-party imports, no CLI imports.

The reporter reads a hook payload from stdin, checks consent, builds
an event from the profile's ``fields`` allowlist only, appends to a
bounded local spool, and (under ``allow`` mode) batches asynchronously
to the profile endpoint with TLS verification.

Subcommands exposed on the same file:

    status   — show whether observation is on, the spool size, and tier.
    pending  — list spooled event IDs not yet delivered.
    export   — dump the entire local spool as JSON to stdout.
    delete   — erase the local spool and consent record.
    disable  — set consent mode to ``off`` in ``.logion/consent.json``.

Exit 0 always on the hook path, regardless of success or failure.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import TypedDict

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Maximum stdin payload size (1 MiB).
MAX_STDIN_BYTES = 1024 * 1024

#: Default maximum spool size in bytes.
DEFAULT_MAX_SPOOL_BYTES = 262_144

#: Default batch size for upload.
DEFAULT_MAX_BATCH = 20

#: Environment variables that disable observation.
_DNT_VARS = ("DO_NOT_TRACK", "LOGION_DO_NOT_TRACK")

#: Values that count as "not set" for DNT variables.
_DNT_FALSE = frozenset({"", "0", "false", "no", "off"})

#: Upload retry backoff base (seconds).
_BACKOFF_BASE = 0.1

#: Maximum upload retries.
_MAX_RETRIES = 3

#: Upload timeout (seconds).
_UPLOAD_TIMEOUT = 5

# ---------------------------------------------------------------------------
# TypedDicts
# ---------------------------------------------------------------------------


class ConsentRecord(TypedDict, total=False):
    """Shape of ``.logion/consent.json``."""

    mode: str  # "off" | "local-only" | "allow"
    scope: str
    profile_digest: str
    installation_id: str


class EventRecord(TypedDict, total=False):
    """A single spooled event."""

    event_id: str
    installation_id: str
    event: str
    resource_id: str
    resource_version: str
    distribution_digest: str
    outcome: str
    duration_bucket: str
    harness: str
    integration_version: str
    timestamp: float
    delivered: bool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _logion_dir(base: Path | None = None) -> Path:
    """Return the ``.logion`` directory, defaulting to CWD."""
    if base is not None:
        return base / ".logion"
    return Path.cwd() / ".logion"


def _consent_path(base: Path | None = None) -> Path:
    return _logion_dir(base) / "consent.json"


def _spool_path(base: Path | None = None) -> Path:
    return _logion_dir(base) / "spool.jsonl"


def _profile_path(base: Path | None = None) -> Path:
    return _logion_dir(base) / "profile.json"


def _dnt_active() -> bool:
    """Return True if a DNT variable is set to a truthy value."""
    for var in _DNT_VARS:
        val = os.environ.get(var, "")
        if val not in _DNT_FALSE:
            return True
    return False


def _load_consent(base: Path | None = None) -> ConsentRecord | None:
    path = _consent_path(base)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(raw, dict):
        return None
    return raw  # type: ignore[return-value]


def _load_profile(base: Path | None = None) -> dict[str, object] | None:
    path = _profile_path(base)
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(raw, dict):
        return None
    return raw


def _event_id(payload: dict[str, object], installation_id: str) -> str:
    """Compute a deterministic event ID from payload + installation."""
    raw = json.dumps(
        {"payload": payload, "installation_id": installation_id},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:32]


def _build_event(
    payload: dict[str, object],
    profile: dict[str, object],
    consent: ConsentRecord,
) -> EventRecord:
    """Build an event from the payload using only the profile's fields.

    A field not in the allowlist never enters memory as part of the
    event.
    """
    allowed: set[str] = set(profile.get("fields", []))  # type: ignore[arg-type,call-overload]
    installation_id = consent.get("installation_id", "")
    eid = _event_id(payload, installation_id)

    event: EventRecord = {
        "event_id": eid,
        "installation_id": installation_id,
        "timestamp": time.time(),
        "delivered": False,
    }

    # Map payload keys to allowed field names.
    field_map: dict[str, str] = {
        "resource_id": "resource_id",
        "resource_version": "resource_version",
        "distribution_digest": "distribution_digest",
        "event": "event",
        "outcome": "outcome",
        "duration_bucket": "duration_bucket",
        "harness": "harness",
        "integration_version": "integration_version",
    }
    for field_name in allowed:
        source_key = field_map.get(field_name, field_name)
        if source_key in payload:
            event[field_name] = str(payload[source_key])  # type: ignore[literal-required]

    # Never include sensitive keys.
    sensitive = frozenset({
        "prompt",
        "file_content",
        "local_path",
        "tool_arguments",
        "tool_results",
        "model_context",
        "secrets",
        "user_identity",
        "transcript_path",
        "tool_input",
        "tool_response",
    })
    for key in sensitive:
        event.pop(key, None)  # type: ignore[arg-type,misc]

    return event


def _append_spool(
    event: EventRecord,
    base: Path | None = None,
    max_spool: int = DEFAULT_MAX_SPOOL_BYTES,
) -> bool:
    """Append *event* to the spool, dropping oldest if over limit.

    Returns True if appended, False if the spool is unavailable.
    """
    spool = _spool_path(base)
    try:
        spool.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False

    line = json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n"
    line_bytes = line.encode("utf-8")

    try:
        # Check current spool size and trim if needed.
        if spool.is_file():
            current = spool.stat().st_size
            if current + len(line_bytes) > max_spool:
                _trim_spool(spool, max_spool, len(line_bytes))
        with spool.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        return False
    return True


def _trim_spool(spool: Path, max_spool: int, incoming: int) -> None:
    """Drop oldest lines until the spool fits the new entry."""
    try:
        lines = spool.read_text(encoding="utf-8").splitlines(keepends=True)
    except OSError:
        return
    drop_count = 0
    while (
        lines
        and sum(len(line.encode("utf-8")) for line in lines) + incoming
        > max_spool
    ):
        lines.pop(0)
        drop_count += 1
    if drop_count > 0:
        # Record the drop count in a metadata line at the top.
        meta = json.dumps(
            {"_drop_count": drop_count, "_trimmed_at": time.time()},
            sort_keys=True,
            separators=(",", ":"),
        )
        with contextlib.suppress(OSError):
            spool.write_text(meta + "\n" + "".join(lines), encoding="utf-8")


def _read_spool(base: Path | None = None) -> list[EventRecord]:
    """Read all events from the spool."""
    spool = _spool_path(base)
    if not spool.is_file():
        return []
    events: list[EventRecord] = []
    try:
        for line in spool.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            obj = json.loads(line)
            if isinstance(obj, dict) and "_drop_count" not in obj:
                events.append(obj)  # type: ignore[arg-type]
    except (json.JSONDecodeError, OSError):
        pass
    return events


def _write_consent(consent: ConsentRecord, base: Path | None = None) -> bool:
    path = _consent_path(base)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(consent, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except OSError:
        return False
    return True


def _delete_spool(base: Path | None = None) -> bool:
    spool = _spool_path(base)
    try:
        if spool.is_file():
            spool.unlink()
    except OSError:
        return False
    return True


def _upload_batch(
    events: list[EventRecord],
    endpoint: str,
) -> bool:
    """Upload a batch of events to the endpoint with TLS verification.

    Returns True on success, False on failure.
    Only HTTPS endpoints are accepted.
    """
    if not endpoint.startswith("https://"):
        return False
    payload = json.dumps(
        {"events": events}, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    ctx = ssl.create_default_context()
    for attempt in range(_MAX_RETRIES):
        try:
            req = urllib.request.Request(
                endpoint,
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(
                req, timeout=_UPLOAD_TIMEOUT, context=ctx
            ) as resp:
                if 200 <= resp.status < 300:
                    return True
        except (urllib.error.URLError, OSError, ssl.SSLError):
            pass
        time.sleep(_BACKOFF_BASE * (2**attempt))
    return False


def _dedup_key(event: EventRecord) -> str:
    """Deduplicate by (event_id, installation_id)."""
    return f"{event.get('event_id', '')}:{event.get('installation_id', '')}"


def _mark_delivered(delivered_ids: set[str], base: Path | None = None) -> None:
    """Mark events as delivered in the spool."""
    spool = _spool_path(base)
    if not spool.is_file():
        return
    events = _read_spool(base)
    changed = False
    for ev in events:
        if ev.get("event_id") in delivered_ids and not ev.get("delivered"):
            ev["delivered"] = True
            changed = True
    if changed:
        try:
            lines = [
                json.dumps(ev, sort_keys=True, separators=(",", ":")) + "\n"
                for ev in events
            ]
            spool.write_text("".join(lines), encoding="utf-8")
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Hook path (stdin → spool → optional upload)
# ---------------------------------------------------------------------------


def _read_and_parse_stdin() -> dict[str, object] | None:
    """Read stdin (bounded), parse JSON, return the payload or None."""
    try:
        raw = sys.stdin.buffer.read(MAX_STDIN_BYTES)
    except Exception:
        return None
    if not raw.strip():
        return None
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _consent_allows(
    base: Path | None,
) -> tuple[str, ConsentRecord, dict[str, object]] | None:
    """Check consent + profile. Return (mode, consent, profile) or None."""
    if _dnt_active():
        return None
    consent = _load_consent(base)
    if consent is None:
        return None
    mode = consent.get("mode", "off")
    if mode == "off":
        return None
    profile = _load_profile(base)
    if profile is None:
        return None
    return mode, consent, profile


def _try_upload(
    profile: dict[str, object],
    base: Path | None,
) -> None:
    """Upload pending events under allow mode."""
    events = _read_spool(base)
    pending = [e for e in events if not e.get("delivered")]
    seen: set[str] = set()
    unique: list[EventRecord] = []
    for ev in pending:
        key = _dedup_key(ev)
        if key not in seen:
            seen.add(key)
            unique.append(ev)

    delivery = profile.get("delivery", {})
    if not isinstance(delivery, dict):
        return
    endpoint = str(delivery.get("endpoint", ""))
    if not endpoint or not endpoint.startswith("https://"):
        return
    max_batch = int(delivery.get("max_batch", DEFAULT_MAX_BATCH))
    delivered: set[str] = set()
    for i in range(0, len(unique), max_batch):
        batch = unique[i : i + max_batch]
        if _upload_batch(batch, endpoint):
            for ev in batch:
                delivered.add(ev.get("event_id", ""))
    if delivered:
        _mark_delivered(delivered, base)


def run_hook(base: Path | None = None) -> int:
    """Main hook entry point — reads stdin, exits 0 always."""
    # 1. Read stdin, bounded to 1 MiB. Parse failure → exit 0 silently.
    payload = _read_and_parse_stdin()
    if payload is None:
        return 0

    # 2. Check consent.
    allowed = _consent_allows(base)
    if allowed is None:
        return 0
    mode, consent, profile = allowed

    # 3. Build event from allowlist only.
    event = _build_event(payload, profile, consent)

    # 4. Append to bounded spool.
    delivery = profile.get("delivery", {})
    max_spool = DEFAULT_MAX_SPOOL_BYTES
    if isinstance(delivery, dict):
        max_spool = int(
            delivery.get("max_spool_bytes", DEFAULT_MAX_SPOOL_BYTES)
        )
    _append_spool(event, base, max_spool)

    # 5. Under local-only, stop here.
    if mode == "local-only":
        return 0

    # 6. Under allow, batch async with retries.
    if mode == "allow":
        _try_upload(profile, base)

    # 7. Exit 0 always.
    return 0


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------


def cmd_status(base: Path | None = None) -> int:
    consent = _load_consent(base)
    mode = "off" if consent is None else consent.get("mode", "off")
    spool = _spool_path(base)
    spool_size = spool.stat().st_size if spool.is_file() else 0
    events = _read_spool(base)
    pending_count = sum(1 for e in events if not e.get("delivered"))
    profile = _load_profile(base)
    tier = "unsupported"
    if profile is not None and mode != "off":
        tier = mode
    print(
        json.dumps(
            {
                "mode": mode,
                "tier": tier,
                "spool_bytes": spool_size,
                "spool_events": len(events),
                "pending": pending_count,
                "dnt": _dnt_active(),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


def cmd_pending(base: Path | None = None) -> int:
    events = _read_spool(base)
    pending = [
        {"event_id": e.get("event_id"), "event": e.get("event")}
        for e in events
        if not e.get("delivered")
    ]
    print(json.dumps(pending, indent=2, sort_keys=True))
    return 0


def cmd_export(base: Path | None = None) -> int:
    events = _read_spool(base)
    print(json.dumps(events, indent=2, sort_keys=True))
    return 0


def cmd_delete(base: Path | None = None) -> int:
    _delete_spool(base)
    consent = _load_consent(base)
    if consent is not None:
        consent["mode"] = "off"
        _write_consent(consent, base)
    print(json.dumps({"deleted": True}, sort_keys=True))
    return 0


def cmd_disable(base: Path | None = None) -> int:
    consent = _load_consent(base)
    if consent is None:
        consent = ConsentRecord(mode="off")
    consent["mode"] = "off"
    _write_consent(consent, base)
    print(json.dumps({"disabled": True}, sort_keys=True))
    return 0


# ---------------------------------------------------------------------------
# CLI dispatch
# ---------------------------------------------------------------------------


def _add_base_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--base",
        type=Path,
        default=None,
        help="Base directory containing .logion/ (default: CWD).",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="report.py",
        description="Logion consented-observation reporter (Python binding).",
    )
    _add_base_arg(parser)
    sub = parser.add_subparsers(dest="command")

    for name, help_text in [
        ("status", "Show observation status."),
        ("pending", "List pending (undelivered) events."),
        ("export", "Export all local events as JSON."),
        ("delete", "Erase local spool and set consent off."),
        ("disable", "Set consent mode to off."),
    ]:
        sp = sub.add_parser(name, help=help_text)
        _add_base_arg(sp)

    args = parser.parse_args(argv)

    base: Path | None = getattr(args, "base", None)

    if args.command == "status":
        return cmd_status(base)
    if args.command == "pending":
        return cmd_pending(base)
    if args.command == "export":
        return cmd_export(base)
    if args.command == "delete":
        return cmd_delete(base)
    if args.command == "disable":
        return cmd_disable(base)

    # No subcommand → hook path (read stdin).
    return run_hook(base)


if __name__ == "__main__":
    sys.exit(main())
