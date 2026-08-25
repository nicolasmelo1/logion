#!/usr/bin/env python3
"""Seed a resource and version for the instrument scenario via the CLI.

Uses the publisher's Logion CLI to create a resource and a version,
then publishes the version so ``logion instrument`` can resolve it.
Outputs the resource_id, version_id, resource title, and publisher
identity as JSON for the scenario's capture mechanism.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", required=True)
    parser.add_argument("--logion-home", required=True)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--base-url", required=True)
    args = parser.parse_args()

    evidence = Path(args.evidence_dir)
    evidence.mkdir(parents=True, exist_ok=True)
    cli = args.cli
    base_env = {
        "LOGION_HOME": args.logion_home,
        "LOGION_API_BASE_URL": args.base_url,
    }

    # Create a resource.
    resource_title = "Publisher Review Skill"
    result = subprocess.run(
        [
            cli,
            "resources",
            "create",
            "--title",
            resource_title,
            "--canonical-uri",
            "github://nicolasmelo1/logion/phase-15-11-1-review-skill",
            "--resource-type",
            "skill",
            "--json",
        ],
        capture_output=True,
        text=True,
        env={**base_env, "PATH": __import__("os").environ.get("PATH", "")},
    )
    if result.returncode != 0:
        sys.stderr.write(f"resource create failed: {result.stderr}\n")
        return result.returncode
    (evidence / "resource-create.json").write_text(
        result.stdout, encoding="utf-8"
    )
    resource_data = json.loads(result.stdout)
    resource_data = resource_data.get("data", resource_data)
    resource_id = str(resource_data.get("id") or "")

    # Create a version.
    version_label = "0.1.0"
    result = subprocess.run(
        [
            cli,
            "resources",
            "versions",
            "create",
            resource_id,
            "--version",
            version_label,
            "--json",
        ],
        capture_output=True,
        text=True,
        env={**base_env, "PATH": __import__("os").environ.get("PATH", "")},
    )
    if result.returncode != 0:
        sys.stderr.write(f"version create failed: {result.stderr}\n")
        return result.returncode
    (evidence / "version-create.json").write_text(
        result.stdout, encoding="utf-8"
    )
    version_data = json.loads(result.stdout)
    version_data = version_data.get("data", version_data)
    version_id = str(version_data.get("id") or "")

    # Get the publisher identity from the resource.
    publisher = resource_data.get("publisher") or {}
    publisher_identity = str(publisher.get("identity") or "did:web:unknown")

    sys.stdout.write(
        json.dumps({
            "resource_id": resource_id,
            "version_id": version_id,
            "resource_title": resource_title,
            "publisher_identity": publisher_identity,
        })
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
