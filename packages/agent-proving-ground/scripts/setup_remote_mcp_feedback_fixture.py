#!/usr/bin/env python3
"""Create a native vendor connector and OAuth-protected remote MCP fixture."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

NPM_NAME = "@acme-vendor/private-mcp-connector"
COMMIT = "1234567890abcdef1234567890abcdef12345678"  # pragma: allowlist secret


def _snapshot(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(
            path.read_bytes()
        ).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def main() -> int:
    workspace = Path(sys.argv[1]).resolve()
    fixture = workspace / "vendor-repo"
    home = workspace / "home"
    logion_home = home / ".logion"
    evidence = fixture / "evidence"
    dsh_home = fixture / ".dsh"
    profile = dsh_home / "profiles" / "vendor"
    installed = profile / "node_modules" / Path(NPM_NAME)
    for directory in (fixture, home, logion_home, evidence, installed):
        directory.mkdir(parents=True, exist_ok=True)
    if not (fixture / ".git").is_dir():
        subprocess.run(
            ["git", "init", "--quiet", "--initial-branch=main", str(fixture)],
            check=True,
        )
    (profile / "package.json").write_text(
        json.dumps(
            {
                "name": "vendor-profile",
                "private": True,
                "dependencies": {NPM_NAME: "1.0.0"},
                "dsh": {"profile": {"bundles": [NPM_NAME]}},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (installed / "package.json").write_text(
        json.dumps(
            {
                "name": NPM_NAME,
                "version": "1.0.0",
                "gitHead": COMMIT,
                "repository": "https://github.com/acme-vendor/private-mcp-connector",
                "mcp": {
                    "endpoint": "http://127.0.0.1:18765/mcp",
                    "authentication": "oauth2",
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    client = installed / "invoke"
    client.write_text(
        "#!/bin/sh\n"
        "curl --fail --silent --output /dev/null "
        "-H 'Authorization: Bearer fixture-access' "
        "-H 'Content-Type: application/json' "
        '--data \'{"method":"tools/call"}\' '
        "http://127.0.0.1:18765/mcp\n",
        encoding="utf-8",
    )
    client.chmod(0o700)
    server = Path(__file__).with_name("remote_mcp_fixture_server.py")
    subprocess.Popen(
        [sys.executable, str(server)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    before = evidence / "vendor-before.json"
    before.write_text(json.dumps(_snapshot(profile), sort_keys=True) + "\n")
    sys.stdout.write(
        json.dumps({
            "fixture_root": str(fixture),
            "isolated_home": str(home),
            "logion_home": str(logion_home),
            "evidence_dir": str(evidence),
            "dsh_home": str(dsh_home),
            "vendor_before": str(before),
        })
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
