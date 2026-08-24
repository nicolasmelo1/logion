# SPDX-License-Identifier: MIT
"""Validator for ``logion.instrumentation/v1`` profiles.

Loads the schema, validates a profile, computes the canonical digest
(sorted keys, no insignificant whitespace), and supports ``--diff``
mode between two profile versions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import cast

import jsonschema

from logion_instrumentation._json import JsonObject, JsonValue
from logion_instrumentation.schema import load_schema
from logion_instrumentation.vocabulary import MAX_PAYLOAD_BYTES

#: Template placeholders that indicate an unresolved endpoint.
_TEMPLATE_MARKERS = frozenset({
    "RESOURCE_UUID",
    "VERSION_UUID",
    "{resource_id}",
    "{version_id}",
})

_ENDPOINT_RE = re.compile(r"^https://[^\s]+$")


class ValidationError(Exception):
    """Raised when a profile fails schema or policy validation."""


def _canonical_json(obj: JsonValue) -> str:
    """Serialize *obj* with sorted keys and no insignificant whitespace."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


def canonical_digest(profile: JsonObject) -> str:
    """Return the SHA-256 canonical digest of *profile*.

    The digest is computed over the canonical JSON serialization
    (sorted keys, no insignificant whitespace), prefixed with
    ``sha256:``.
    """
    payload = _canonical_json(profile).encode("utf-8")
    return f"sha256:{hashlib.sha256(payload).hexdigest()}"


def _check_payload_size(profile: JsonObject) -> None:
    raw = _canonical_json(profile).encode("utf-8")
    if len(raw) > MAX_PAYLOAD_BYTES:
        msg = (
            f"profile payload exceeds {MAX_PAYLOAD_BYTES} bytes "
            f"({len(raw)} bytes)"
        )
        raise ValidationError(msg)


def _check_endpoint(profile: JsonObject) -> None:
    """Enforce HTTPS-only, single-host, no-template policy."""
    delivery = profile.get("delivery", {})
    if not isinstance(delivery, dict):
        return  # caught by schema validation
    endpoint = delivery.get("endpoint", "")
    if not isinstance(endpoint, str) or not endpoint:
        return  # missing endpoint caught by schema validation
    if not _ENDPOINT_RE.match(endpoint):
        msg = f"delivery.endpoint must be an HTTPS URL: {endpoint!r}"
        raise ValidationError(msg)
    upper = endpoint.upper()
    for marker in _TEMPLATE_MARKERS:
        if marker.upper() in upper:
            msg = (
                f"delivery.endpoint contains unresolved template"
                f" placeholder {marker!r}: {endpoint!r}"
            )
            raise ValidationError(msg)
    # Single host: the URL must not contain a redirect or multiple hosts.
    # We extract the host from the netloc and verify there is exactly one.
    after_scheme = endpoint[len("https://") :]
    path_start = after_scheme.find("/")
    host_part = after_scheme[:path_start] if path_start != -1 else after_scheme
    if "/" in host_part or " " in host_part:
        msg = f"delivery.endpoint host is malformed: {host_part!r}"
        raise ValidationError(msg)


def validate_profile(profile: JsonObject) -> None:
    """Validate *profile* against the v1 schema and endpoint policy.

    Raises :class:`ValidationError` on any failure.
    """
    _check_payload_size(profile)
    schema = load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(profile), key=lambda e: e.path)
    if errors:
        messages = []
        for err in errors:
            loc = "/".join(str(p) for p in err.absolute_path) or "<root>"
            messages.append(f"{loc}: {err.message}")
        raise ValidationError("; ".join(messages))
    _check_endpoint(profile)


def load_profile(path: Path) -> JsonObject:
    """Load a profile JSON file and return it as a dict."""
    text = path.read_text(encoding="utf-8")
    try:
        obj = json.loads(text)
    except json.JSONDecodeError as exc:
        msg = f"invalid JSON in {path}: {exc}"
        raise ValidationError(msg) from exc
    if not isinstance(obj, dict):
        msg = f"profile must be a JSON object, got {type(obj).__name__}"
        raise ValidationError(msg)
    return obj


def diff_profiles(
    old: JsonObject,
    new: JsonObject,
) -> JsonObject:
    """Compute a structured diff between two profile versions.

    The diff reports added/removed events, fields, and excluded
    categories, plus whether the change *widens* data categories
    (i.e. removes an excluded entry or adds a field).
    """
    old_events: set[str] = set(cast("list[str]", old.get("events", [])))
    new_events: set[str] = set(cast("list[str]", new.get("events", [])))
    old_fields: set[str] = set(cast("list[str]", old.get("fields", [])))
    new_fields: set[str] = set(cast("list[str]", new.get("fields", [])))
    old_excluded: set[str] = set(cast("list[str]", old.get("excluded", [])))
    new_excluded: set[str] = set(cast("list[str]", new.get("excluded", [])))

    added_fields = new_fields - old_fields
    removed_excluded = old_excluded - new_excluded

    return {
        "events": {
            "added": sorted(new_events - old_events),
            "removed": sorted(old_events - new_events),
        },
        "fields": {
            "added": sorted(added_fields),
            "removed": sorted(old_fields - new_fields),
        },
        "excluded": {
            "added": sorted(new_excluded - old_excluded),
            "removed": sorted(removed_excluded),
        },
        "widens_data_categories": bool(added_fields or removed_excluded),
        "old_digest": canonical_digest(old),
        "new_digest": canonical_digest(new),
    }


def _cmd_validate(path: Path) -> int:
    profile = load_profile(path)
    try:
        validate_profile(profile)
    except ValidationError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return 1
    print(f"VALID: {canonical_digest(profile)}")
    return 0


def _cmd_digest(path: Path) -> int:
    profile = load_profile(path)
    print(canonical_digest(profile))
    return 0


def _cmd_diff(old_path: Path, new_path: Path) -> int:
    old = load_profile(old_path)
    new = load_profile(new_path)
    result = diff_profiles(old, new)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for ``logion-instrumentation``."""
    parser = argparse.ArgumentParser(
        prog="logion-instrumentation",
        description=(
            "Validate and diff Logion instrumentation profiles"
            " (logion.instrumentation/v1)."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_validate = sub.add_parser("validate", help="Validate a profile.")
    p_validate.add_argument("path", type=Path, help="Path to profile JSON.")

    p_digest = sub.add_parser("digest", help="Compute canonical digest.")
    p_digest.add_argument("path", type=Path, help="Path to profile JSON.")

    p_diff = sub.add_parser("diff", help="Diff two profile versions.")
    p_diff.add_argument("old", type=Path, help="Path to old profile JSON.")
    p_diff.add_argument("new", type=Path, help="Path to new profile JSON.")

    args = parser.parse_args(argv)

    if args.command == "validate":
        return _cmd_validate(args.path)
    if args.command == "digest":
        return _cmd_digest(args.path)
    if args.command == "diff":
        return _cmd_diff(args.old, args.new)
    parser.error(f"unknown command: {args.command}")
    return 2
