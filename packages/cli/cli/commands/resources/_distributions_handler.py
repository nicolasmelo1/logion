# SPDX-License-Identifier: MIT
"""Handler for ``resources distributions``."""

from __future__ import annotations

import argparse
import sys

from cli._config import resolve_config_from_args
from cli._context import make_client
from cli._errors import handle_error, handle_validation_error
from cli._json import child, children
from cli._output import emit_json, to_data

from ._acquire_plan import normalize_versions
from ._distribution_entries import _distribution_entries


def handle_resources_distributions(args: argparse.Namespace) -> int:
    """List acquisition channels available for a resource version."""
    config = resolve_config_from_args(args)
    client = make_client(config)
    try:
        version_payload = to_data(
            client.v1.resources.versions(resource_id=args.resource_id)
        )

        versions = normalize_versions(version_payload)
        if not versions:
            return handle_validation_error(
                "no resource version available",
                json_output=config.json_output,
            )
        version_id = getattr(args, "version", None) or str(
            versions[0].get("id") or versions[0].get("version_id")
        )
        plan = to_data(
            client.v1.resources.acquisition_plan(
                resource_id=args.resource_id,
                version_id=version_id,
                channel="auto",
            )
        )
        payload = {
            "resource_id": args.resource_id,
            "version_id": version_id,
            "selected_channel": plan.get("selected_channel"),
            "distributions": _distribution_entries(
                client, args.resource_id, version_id, plan
            ),
        }
        if config.json_output:
            emit_json("logion.resources.distributions", payload)
        else:
            out = sys.stdout
            out.write(f"Resource: {payload['resource_id']}\n")
            out.write(f"Version:  {payload['version_id']}\n")
            for dist in children(payload, "distributions"):
                marker = " (selected)" if dist["selected"] else ""
                out.write(f"  - {dist['channel']}{marker}\n")
                if not dist["available"]:
                    out.write(f"      unavailable: {dist['reason']}\n")
                    continue
                native = child(dist, "native")
                if native.get("tool"):
                    out.write(
                        f"      native: {native['tool']} "
                        f"{native.get('tested_version') or '?'}\n"
                    )
                if dist.get("expected"):
                    out.write(f"      expected: {dist['expected']}\n")
    except Exception as exc:
        return handle_error(
            exc, json_output=config.json_output, handle_validation=True
        )
    else:
        return 0
    finally:
        client.close()
