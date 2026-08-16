# SPDX-License-Identifier: MIT
"""Channel listing for ``logion resources distributions``.

Each listed channel is server-reported: the selected one comes from the
version's acquisition plan, and every alternative is resolved by asking
the server for that channel's own plan. A channel the server will not
plan is reported as unavailable with its reason rather than assumed
enabled.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from cli._json import JsonObject, child, elements
from cli._lazy_import import LazyModule
from cli._output import to_data

if TYPE_CHECKING:
    import logion
else:
    logion = LazyModule("logion")
#: Bounds the per-channel plan fetches behind `resources distributions`.
_MAX_ALTERNATIVE_CHANNELS = 8


def _plan_entry(
    plan: JsonObject, channel: str, *, selected: bool
) -> JsonObject:
    return {
        "channel": channel,
        "selected": selected,
        "available": True,
        "distribution_id": plan.get("distribution_id"),
        "content_digest": plan.get("content_digest"),
        "integrity": child(plan, "integrity"),
        "license": child(plan, "license"),
        "entitlement": child(plan, "entitlement"),
        "expected": child(plan, "expected"),
        "native": child(plan, "native"),
        "warnings": list(elements(plan, "warnings")),
    }


def _distribution_entries(
    client: logion.LogionClient,
    resource_id: str,
    version_id: str,
    selected_plan: JsonObject,
) -> list[JsonObject]:
    """List the channels the server actually offers for a version.

    Every entry is server-reported. Alternatives are resolved by asking
    the server for each channel's plan rather than assuming a bare channel
    name is enabled — an alternative the server will not plan is reported
    as unavailable with its reason.
    """
    selected_channel = str(selected_plan.get("selected_channel") or "")
    entries = [_plan_entry(selected_plan, selected_channel, selected=True)]
    alternatives = [
        str(alt)
        for alt in (elements(selected_plan, "alternatives"))
        if str(alt) and str(alt) != selected_channel
    ]
    for channel in alternatives[:_MAX_ALTERNATIVE_CHANNELS]:
        try:
            plan = to_data(
                client.v1.resources.acquisition_plan(
                    resource_id=resource_id,
                    version_id=version_id,
                    channel=channel,
                )
            )
        except Exception as exc:
            entries.append({
                "channel": channel,
                "selected": False,
                "available": False,
                "reason": str(exc),
            })
            continue
        if not isinstance(plan, dict) or not plan.get("distribution_id"):
            entries.append({
                "channel": channel,
                "selected": False,
                "available": False,
                "reason": "server returned no distribution for this channel",
            })
            continue
        entries.append(_plan_entry(plan, channel, selected=False))
    dropped = len(alternatives) - len(alternatives[:_MAX_ALTERNATIVE_CHANNELS])
    if dropped > 0:
        entries.append({
            "channel": None,
            "selected": False,
            "available": False,
            "reason": f"{dropped} further alternative channel(s) not queried",
        })
    return entries
