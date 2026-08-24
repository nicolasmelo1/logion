# SPDX-License-Identifier: MIT
"""Handler for ``logion instrument`` — the publisher-side generator.

Resolves a canonical ResourceVersion from the API, emits a projection
tree per target, computes digests, resolves the tier per client, writes
``capability.json``, and prints the plan and diff under ``--dry-run``.

Approval-gated write, zero-write dry run. Never publishes a package,
widens permissions, or enables network delivery without explicit
publisher approval.

Plan building, execution, and API resolution live in ``_plan.py`` to
keep this module under the architecture test's 250-line limit.
"""

from __future__ import annotations

import argparse

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error, handle_validation_error
from cli._json import child

from ._constants import EVENT_CHOICES
from ._plan import (
    build_plan,
    execute_plan,
    render_dry_run,
    resolve_output_dir,
    resolve_profile,
    validate_profile_if_available,
)
from ._resolve import resolve_resource_version


def handle_instrument(args: argparse.Namespace) -> int:
    """Execute ``logion instrument RESOURCE_VERSION --dry-run``."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        targets = getattr(args, "targets", [])
        if not targets:
            return handle_validation_error(
                "at least one --target is required",
                json_output=config.json_output,
            )
        events = getattr(args, "events", None) or list(EVENT_CHOICES)

        resource, version = resolve_resource_version(
            client, args.resource_version
        )
        publisher_identity = str(
            child(resource, "publisher").get("identity") or "did:web:unknown"
        )

        profile = resolve_profile(
            args,
            resource,
            version,
            events,
            publisher_identity,
            config.json_output,
        )
        if profile is None:
            return 2  # validation error already emitted

        validate_profile_if_available(profile)

        output_dir = resolve_output_dir(args, resource, version)
        plan = build_plan(
            args,
            resource,
            version,
            profile,
            publisher_identity,
            output_dir,
            targets,
            events,
        )

        if plan["dry_run"]:
            render_dry_run(config.json_output, plan)
            return 0

        return execute_plan(
            args,
            config,
            plan,
            resource,
            version,
            profile,
            publisher_identity,
        )
    except Exception as exc:
        return handle_error(
            exc, json_output=config.json_output, handle_validation=True
        )
    finally:
        client.close()
