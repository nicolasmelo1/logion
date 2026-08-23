# SPDX-License-Identifier: MIT
"""Consent-gated upload of spooled observations as usage receipts.

This is the only place in the CLI where a local observation becomes a
network write, which is why the consent check lives here rather than in
the spool: everything before this point stays on the machine, whatever
the mode.
"""

from __future__ import annotations

import argparse
import sys

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error
from cli._json import JsonObject, opt_str
from cli._output import emit_json, to_data, to_object
from cli._pseudonymous_subject import build_receipt_proof
from cli.integrations_state import AUTO, effective_mode, may_upload
from cli.usage.observations import (
    list_pending_observations,
    with_group_ids,
)
from cli.usage.tombstones import receipt_tombstone, record_receipt

from .handlers import _parse_since

#: Recorded with every receipt so a row can be traced back to the
#: consent policy that permitted it.
CONSENT_POLICY_VERSION = "logion.consent.v1"


def _upload_blocked(harness: str, *, assume_yes: bool) -> str | None:
    """Why this upload may not proceed, or ``None`` when it may."""
    mode = effective_mode(harness)
    if not may_upload(harness):
        return f"upload_not_consented (mode: {mode})"
    if mode != AUTO and not assume_yes:
        return (
            f"mode {mode} requires explicit confirmation:"
            " re-run with --yes after reviewing the payload"
        )
    return None


def _submit_one(
    client: object,
    obs: JsonObject,
    args: argparse.Namespace,
    *,
    api_key: str | None,
) -> str:
    """Submit one receipt and return the id the API assigned it."""
    kwargs: JsonObject = {
        "observation_id": opt_str(obs, "observation_id", ""),
        "task_class": opt_str(obs, "task_class") or args.task_class,
        "acquisition_channel": opt_str(obs, "acquisition_channel", ""),
        "consent_policy_digest": CONSENT_POLICY_VERSION,
        "harness": opt_str(obs, "harness") or None,
        "outcome": opt_str(obs, "outcome") or args.outcome,
        "observed_at": opt_str(obs, "observed_at") or None,
        "duration_bucket": opt_str(obs, "duration_bucket"),
        "integration_version": opt_str(obs, "integration_version"),
    }
    if not api_key:
        kwargs.update(
            build_receipt_proof({
                "resource_id": opt_str(obs, "resource_id", ""),
                "version_id": opt_str(obs, "version_id", ""),
                "observation_id": opt_str(obs, "observation_id", ""),
                "task_class": opt_str(obs, "task_class") or args.task_class,
                "acquisition_channel": opt_str(obs, "acquisition_channel", ""),
                "consent_policy_digest": CONSENT_POLICY_VERSION,
                "harness": opt_str(obs, "harness") or None,
                "outcome": opt_str(obs, "outcome") or args.outcome,
                "observed_at": opt_str(obs, "observed_at") or None,
                "duration_bucket": opt_str(obs, "duration_bucket"),
                "integration_version": opt_str(obs, "integration_version"),
            })
        )
    result = client.v1.usage_receipts.submit(  # type: ignore[attr-defined]
        opt_str(obs, "resource_id", ""),
        opt_str(obs, "version_id", ""),
        **kwargs,
    )
    return opt_str(to_object(result), "id", "")


def handle_usage_upload(args: argparse.Namespace) -> int:
    """Upload spooled observations as narrow usage receipts."""
    config = resolve_config_from_args(args)
    try:
        since_seconds = _parse_since(getattr(args, "since", "24h"))
        observations = with_group_ids(
            list_pending_observations(since_seconds=since_seconds)
        )
        blocked: dict[str, str | None] = {}
        uploaded: list[JsonObject] = []
        skipped: list[JsonObject] = []
        client = make_client(config)
        try:
            for obs in observations:
                harness = opt_str(obs, "harness", "")
                if harness not in blocked:
                    blocked[harness] = _upload_blocked(
                        harness, assume_yes=getattr(args, "yes", False)
                    )
                observation_id = opt_str(obs, "observation_id", "")
                reason = blocked[harness]
                if reason is not None:
                    skipped.append({
                        "observation_id": observation_id,
                        "reason": reason,
                    })
                    continue
                already = receipt_tombstone(observation_id)
                if already is not None:
                    skipped.append({
                        "observation_id": observation_id,
                        "reason": "already_uploaded",
                        "receipt_id": already,
                    })
                    continue
                receipt_id = _submit_one(
                    client, obs, args, api_key=config.api_key
                )
                if receipt_id:
                    record_receipt(observation_id, receipt_id)
                uploaded.append({
                    "observation_id": observation_id,
                    "receipt_id": receipt_id,
                })
        finally:
            client.close()
        _report(config.json_output, uploaded, skipped)
    except Exception as exc:
        return handle_error(exc)
    return 0


def _report(
    json_output: bool,
    uploaded: list[JsonObject],
    skipped: list[JsonObject],
) -> None:
    if json_output:
        emit_json(
            "logion.usage.upload",
            {"uploaded": to_data(uploaded), "skipped": to_data(skipped)},
        )
        return
    sys.stdout.write(
        f"Uploaded {len(uploaded)} receipt(s); skipped {len(skipped)}.\n"
    )
    for entry in skipped:
        sys.stdout.write(
            f"  skipped {entry.get('observation_id', '')}:"
            f" {entry.get('reason', '')}\n"
        )
