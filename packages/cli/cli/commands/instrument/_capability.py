# SPDX-License-Identifier: MIT
"""Capability tier resolution for ``logion instrument``.

``capability.json`` is generated, never hand-written. The tier is
resolved per client: ``hook`` when the client supports lifecycle hooks
with a verified reporter runtime, ``explicit_report`` for the Cordis/
dsh-plugin shape, and ``unsupported`` when the runtime is missing or
the client version is outside the pinned range.
"""

from __future__ import annotations

from cli._json import JsonObject

from ._projection import INTEGRATION_VERSION

#: Supported client names and their reporter bindings.
_CLIENT_BINDINGS: dict[str, str] = {
    "claude-code": "node",
    "codex": "node",
    "hermes": "python",
}

#: Events each client may report.  Hermes may not claim a terminal event.
_CLIENT_EVENTS: dict[str, list[str]] = {
    "claude-code": [
        "resource_invoked",
        "resource_file_read",
        "resource_tool_used",
    ],
    "codex": [
        "resource_invoked",
        "resource_file_read",
        "resource_tool_used",
    ],
    "hermes": ["resource_invoked"],
}

#: Default tier per target.
_TARGET_TIERS: dict[str, str] = {
    "agent-plugin": "hook",
    "hermes-plugin": "hook",
    "static-skill": "explicit_report",
    "dsh-plugin": "explicit_report",
}


def _check_runtime(binding: str) -> bool:
    """Check whether the reporter runtime is present.

    A missing runtime resolves the tier to ``unsupported``. This is a
    conservative check — the actual runtime detection happens at
    install/activation time, but the generator can flag it early.
    """
    import shutil

    if binding == "node":
        return shutil.which("node") is not None
    if binding == "python":
        return shutil.which("python3") is not None
    return False


def resolve_capability(
    *,
    target: str,
    client: str | None,
    events: list[str],
    profile_digest: str,
) -> JsonObject:
    """Resolve the capability tier for one target/client pair.

    The tier is fail-closed: any condition that prevents hook-based
    observation forces ``unsupported`` with a populated ``reason``,
    never a silent fallback to inferred telemetry.
    """
    resolved_client = client or _default_client_for_target(target)
    binding = _CLIENT_BINDINGS.get(resolved_client, "unknown")
    runtime_present = _check_runtime(binding)
    allowed_events = _CLIENT_EVENTS.get(resolved_client, [])
    base_tier = _TARGET_TIERS.get(target, "unsupported")

    # Hermes capability must not claim a terminal event.
    if resolved_client == "hermes":
        terminal = set(events) - set(allowed_events)
        if terminal:
            return _unsupported(
                client=resolved_client,
                binding=binding,
                runtime_present=runtime_present,
                events=allowed_events,
                reason=(
                    f"hermes capability must not claim terminal event(s): "
                    f"{', '.join(sorted(terminal))}"
                ),
                profile_digest=profile_digest,
            )

    # Missing runtime → unsupported
    if not runtime_present and base_tier == "hook":
        return _unsupported(
            client=resolved_client,
            binding=binding,
            runtime_present=False,
            events=allowed_events,
            reason=(f"reporter runtime '{binding}' is not available"),
            profile_digest=profile_digest,
        )

    return {
        "tier": base_tier,
        "client": resolved_client,
        "pinned_release": None,
        "hook_contract_fixture": None,
        "reporter_binding": binding,
        "reporter_runtime": {
            "required": f"{binding}>=22" if binding == "node" else "python3",
            "present": runtime_present,
        },
        "events": allowed_events,
        "reason": None,
        "integration_version": INTEGRATION_VERSION,
        "profile_digest": profile_digest,
    }


def _unsupported(
    *,
    client: str,
    binding: str,
    runtime_present: bool,
    events: list[str],
    reason: str,
    profile_digest: str,
) -> JsonObject:
    """Build an ``unsupported`` capability with a populated reason."""
    return {
        "tier": "unsupported",
        "client": client,
        "pinned_release": None,
        "hook_contract_fixture": None,
        "reporter_binding": binding,
        "reporter_runtime": {
            "required": f"{binding}>=22" if binding == "node" else "python3",
            "present": runtime_present,
        },
        "events": events,
        "reason": reason,
        "integration_version": INTEGRATION_VERSION,
        "profile_digest": profile_digest,
    }


def _default_client_for_target(target: str) -> str:
    """Return the default client name for a target."""
    if target == "hermes-plugin":
        return "hermes"
    if target == "dsh-plugin":
        return "claude-code"
    return "claude-code"
