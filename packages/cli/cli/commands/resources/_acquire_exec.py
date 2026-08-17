# SPDX-License-Identifier: MIT
"""Executable ``logion resources acquire`` (non-dry-run) path.

Executes the validated server plan against the resolved harness scope using
the channel adapter. Writes a schema v1 receipt under $LOGION_HOME/inventory
only after the artifact verifies. Asks explicit confirmation unless --yes was
supplied by an already-approved non-interactive caller.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

from cli import _receipts
from cli._json import JsonObject, child, opt_str, strings
from cli._lazy_import import LazyModule

if TYPE_CHECKING:
    import logion
else:
    logion = LazyModule("logion")
from ._channels.base import ChannelAdapter
from ._channels.dsh import DshChannelAdapter
from ._channels.hf import HfAdapter
from ._channels.logion_bundle import LogionBundleAdapter
from ._channels.npx_plugins import NpxPluginsAdapter
from ._channels.npx_skills import NpxSkillsAdapter


def run_acquisition(
    *,
    client: logion.LogionClient,
    plan: JsonObject,
    scope: str,
    harness: str,
    destination: Path,
    scope_root: Path,
    relative_target_path: str,
    resource_type: str,
    assume_yes: bool,
    json_output: bool = False,
) -> JsonObject:
    """Execute the validated plan and return the persisted receipt."""
    _display_plan(plan, destination, json_output=json_output)
    if not assume_yes:
        if not sys.stdin.isatty():
            raise RuntimeError(
                "acquisition requires confirmation; pass --yes in "
                "non-interactive mode after displaying the plan"
            )
        answer = input("Proceed with acquisition? [y/N] ").strip().lower()
        if answer not in {"y", "yes"}:
            raise RuntimeError("acquisition declined")

    adapter = _adapter_for(
        opt_str(plan, "selected_channel", ""), client=client
    )
    outcome = adapter.acquire(
        plan=plan, destination=destination, scope_root=scope_root
    )

    native_evidence = outcome.native_evidence
    effective_relative_target_path = relative_target_path
    effective_target_path = destination
    if outcome.installed_paths and plan["selected_channel"] != "logion_bundle":
        first_path = Path(outcome.installed_paths[0])
        effective_relative_target_path = first_path.as_posix()
        effective_target_path = scope_root / first_path
    receipt: JsonObject = {
        "schema_version": _receipts.RECEIPT_SCHEMA_VERSION,
        "resource_id": plan["resource_id"],
        "version_id": plan["version_id"],
        "distribution_id": plan["distribution_id"],
        "resource_type": resource_type,
        "content_digest": plan["content_digest"],
        "channel": plan["selected_channel"],
        "upstream_locator": (child(plan, "native")).get(
            "upstream_locator", ""
        ),
        "harness": harness,
        "scope_kind": scope,
        "scope_id": _receipts.scope_id_for_target(scope, scope_root),
        "installation_id": _receipts.installation_id_for(
            _receipts.scope_id_for_target(scope, scope_root),
            str(effective_relative_target_path),
        ),
        "target_path": str(effective_target_path),
        "relative_target_path": str(effective_relative_target_path),
        "installed_paths": outcome.installed_paths,
        "projection_paths": outcome.projection_paths,
        "acquired_at": _receipts.now_rfc3339(),
        "verified_at": _receipts.now_rfc3339(),
        "verification": outcome.verification,
    }
    if native_evidence is not None:
        receipt["native_evidence"] = native_evidence
        receipt["native_receipt_digest"] = _receipts.native_receipt_digest(
            native_evidence
        )
    _receipts.save_receipt(receipt)
    return receipt


def _adapter_for(
    channel: str, *, client: logion.LogionClient
) -> ChannelAdapter:
    if channel == "logion_bundle":
        return LogionBundleAdapter(client=client)
    if channel == "npx_skills":
        return NpxSkillsAdapter()
    if channel == "npx_plugins":
        return NpxPluginsAdapter()
    if channel == "hf":
        return HfAdapter()
    if channel == "dsh":
        return DshChannelAdapter()
    raise RuntimeError(
        f"channel {channel!r} is not supported by this CLI version"
    )


def _display_plan(
    plan: JsonObject, destination: Path, *, json_output: bool
) -> None:
    out = sys.stderr if json_output else sys.stdout
    out.write("\nAcquisition plan:\n")
    out.write(f"  channel:    {plan['selected_channel']}\n")
    out.write(f"  digest:     {plan['content_digest']}\n")
    license_info = child(plan, "license")
    out.write(
        f"  license:    {license_info.get('spdx') or 'unknown'}"
        f" (redistributable={license_info.get('redistribution_allowed')})\n"
    )
    entitlement = child(plan, "entitlement")
    if entitlement.get("required"):
        out.write(f"  entitlement: {entitlement.get('status')}\n")
    expected = child(plan, "expected")
    if expected.get("bytes") is not None:
        out.write(f"  bytes:      {expected['bytes']}\n")
    native = child(plan, "native")
    if native.get("argv"):
        out.write(f"  argv:       {' '.join(strings(native, 'argv'))}\n")
    permissions = child(plan, "permissions")
    out.write(
        f"  permissions: network={permissions.get('network')}"
        f" tools={permissions.get('tools')}"
        f" secrets={permissions.get('secrets')}\n"
    )
    out.write(f"  installs to: {destination}\n\n")
