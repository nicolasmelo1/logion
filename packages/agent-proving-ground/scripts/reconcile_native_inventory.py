#!/usr/bin/env python3
"""Reconcile the agent's native installation into local inventory.

This step is bookkeeping, not the thing the scenario proves. The phase
before it asks the agent to install a skill through the upstream package
manager; whether it did is decided by reading the reconcile report, and
that report is the same document whoever types the command. Asking the
agent to type it made a deterministic check depend on the agent
remembering a second, unrelated instruction — observed live at roughly one
run in four, where the install had landed and the phase still failed
because no report was written. Worse, the missing file was reported as a
reconciliation that "left unresolved, ambiguous, or drifted entries",
which reads as a product defect.

So the rig runs it. What still depends on the agent is exactly what the
phase is for: that the installation is really on disk, under this scope,
on the expected channel. A reconcile the rig runs cannot invent a match
that is not there — the assertion re-checks every matched entry against
the filesystem.

The CLI invoked here is the artifact the rig installed into the agent's
role tree, not the source checkout, so the report is the one a user's own
command would produce. Credentials come from the role key store, the same
place the seed hook takes them; local hooks are given no secrets in their
environment on purpose.

Usage:
  reconcile_native_inventory.py --cli PATH --cwd ROOT --evidence-dir DIR
                               --logion-home DIR --harness NAME
                               [--role buyer] [--scope repo-root]
                               [--from skills] [--base-url URL]
                               [--artifact-name reconcile-xpto.json]

Emits one JSON line naming the artifact it wrote.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


def _api_key(role: str) -> str:
    """The role's API key, read from the store the runner points at."""
    path = os.environ.get("LOGION_PROVING_GROUND_ROLE_KEYS_FILE")
    if not path:
        raise SystemExit(
            "LOGION_PROVING_GROUND_ROLE_KEYS_FILE is required so the "
            "reconcile runs as the same role as the agent whose "
            "installation it is reconciling"
        )
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    value = raw.get(role)
    if isinstance(value, dict):
        value = value.get("api_key")
    if not isinstance(value, str) or not value:
        raise SystemExit(f"role key store has no api_key for role {role!r}")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cli", required=True)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--evidence-dir", required=True)
    parser.add_argument("--logion-home", required=True)
    parser.add_argument("--harness", required=True)
    parser.add_argument("--role", default="buyer")
    parser.add_argument("--scope", default="repo-root")
    parser.add_argument("--source", "--from", dest="source", default="skills")
    parser.add_argument("--base-url", default="")
    parser.add_argument("--artifact-name", default="reconcile-xpto.json")
    args = parser.parse_args(argv)

    cli = Path(args.cli)
    if not cli.is_file():
        raise SystemExit(
            f"no installed CLI at {cli}; the rig did not put `logion` on the "
            "agent's PATH, so no reconcile can run the artifact under test"
        )
    root = Path(args.cwd).resolve()
    if not root.is_dir():
        raise SystemExit(f"scope root is not a directory: {root}")
    evidence = Path(args.evidence_dir).resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    artifact = evidence / args.artifact_name

    base_url = args.base_url or os.environ.get("LOGION_API_BASE_URL", "")
    if not base_url:
        raise SystemExit(
            "no API base URL: pass --base-url or set LOGION_API_BASE_URL"
        )

    env = {
        **os.environ,
        "LOGION_HOME": str(Path(args.logion_home).resolve()),
        "LOGION_BASE_URL": base_url,
        "LOGION_API_KEY": _api_key(args.role),
    }
    cmd = [
        str(cli),
        "resources",
        "reconcile",
        "--from",
        args.source,
        "--harness",
        args.harness,
        "--scope",
        args.scope,
        "--cwd",
        str(root),
        "--json",
        # First-run onboarding writes to stdout, which would land inside the
        # artifact and make the envelope unreadable.
        "--no-onboarding",
    ]
    proc = subprocess.run(
        cmd, cwd=str(root), env=env, capture_output=True, text=True
    )
    # Written before the exit code is judged: a reconcile that failed is
    # still the evidence a reader needs, and an absent file is the one
    # symptom this whole script exists to remove.
    artifact.write_text(proc.stdout, encoding="utf-8")
    if proc.returncode != 0:
        raise SystemExit(
            f"`logion resources reconcile` exited {proc.returncode}: "
            f"{proc.stderr.strip()[:600]}"
        )

    sys.stdout.write(
        json.dumps({
            "reconcile_artifact": str(artifact),
            "harness": args.harness,
            "scope": args.scope,
            "source": args.source,
        })
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
