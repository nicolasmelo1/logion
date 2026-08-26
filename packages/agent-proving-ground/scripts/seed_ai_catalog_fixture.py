#!/usr/bin/env python3
"""Stand up the world the AI Catalog / ARD scenario is run against.

Three things have to exist before the operator agent can do anything:
the node's discovery surfaces have to be switched on, an ecosystem
outside the node has to be reachable, and the node has to already hold
the entry the consumer will later discover.

The last one is deliberate. The scenario's claim is not "ingestion can
create a resource" -- it is that crawling the same catalog twice adds it
once. Seeding the entry first means both of the agent's crawls are
re-crawls, which is the case the duplicate-identity bug would actually
show up in.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import ai_catalog_fixture_server as fixture
import seed_acquisition_fixture as base

#: Every flag the scenario's surfaces sit behind. Off by default, which
#: is correct for production and useless for a proving run.
REQUIRED_FLAGS = (
    "resource_read_surface",
    "ai_catalog.public",
    "ai_catalog.ingestion",
    "ard.discovery",
    "ard.connectors_sync",
)

DEFAULT_DATABASE_URL = "postgresql://logion:logion@localhost:5433/logion"


def _devrig_env_files() -> list[Path]:
    """Where the rig may have written its environment down.

    Derived from this repository's own location rather than named: the
    checkout that drives the rig sits beside or above it, and this file
    ships in a public repository that must not refer to it.
    """
    repo_root = Path(
        os.environ.get("LOGION_PUBLIC_REPO_PATH")
        or Path(__file__).resolve().parents[3]
    )
    return [
        repo_root / ".devrig" / "devrig.env",
        repo_root.parent / ".devrig" / "devrig.env",
    ]


def _database_url() -> str:
    """Find the dev rig's database, preferring what the rig wrote down."""
    env_url = os.environ.get("LOGION_DATABASE_URL")
    if not env_url:
        for env_file in _devrig_env_files():
            if not env_file.is_file():
                continue
            for line in env_file.read_text(encoding="utf-8").splitlines():
                key, _, value = line.partition("=")
                if key.strip() == "LOGION_DATABASE_URL":
                    env_url = value.strip()
                    break
            if env_url:
                break
    url = env_url or DEFAULT_DATABASE_URL
    # SQLAlchemy's driver suffix is not a libpq URL.
    return url.replace("postgresql+psycopg://", "postgresql://")


def _enable_flags() -> None:
    """Turn on the flags, failing loudly rather than half-way.

    A run that starts with three of five flags set produces assertion
    failures that read like product defects.
    """
    values = ", ".join(f"('{flag}', true)" for flag in REQUIRED_FLAGS)
    statement = (
        f"INSERT INTO feature_flags (key, enabled) VALUES {values} "
        "ON CONFLICT (key) DO UPDATE SET enabled = true;"
    )
    result = subprocess.run(
        ["psql", _database_url(), "-v", "ON_ERROR_STOP=1", "-c", statement],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"could not enable feature flags: {result.stderr.strip()}"
        )


def _start_fixture_server() -> None:
    """Start the stand-in ecosystem, and prove it answered."""
    server = Path(__file__).with_name("ai_catalog_fixture_server.py")
    subprocess.Popen(
        [sys.executable, str(server)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    catalog_url = f"{fixture.ORIGIN}/fixture-catalog.json"
    for _ in range(50):
        try:
            with urllib.request.urlopen(catalog_url, timeout=1) as response:
                if response.status == 200:
                    return
        except (urllib.error.URLError, OSError):
            time.sleep(0.1)
    raise SystemExit(f"fixture server never answered at {catalog_url}")


def _ingest_seed_entries(api: base.Api) -> list[dict]:
    """Put the two well-formed fixture entries into the node.

    The malformed third entry is left out: it exists to be refused by
    the agent's crawl, and refusing it here would spend the evidence
    before the run starts.
    """
    catalog: dict = fixture.CATALOG
    entries = [
        {
            "identifier": entry["identifier"],
            "type": entry["type"],
            "title": entry.get("displayName", ""),
            "summary": entry.get("description"),
            "tags": list(entry.get("tags", [])),
            "publisher": (entry.get("publisher") or {}).get("displayName"),
        }
        for entry in catalog["entries"]
        if "data" not in entry
    ]
    payload = api.expect(
        "POST",
        "/v1/resources:ingest-catalog",
        body={
            "source_uri": f"{fixture.ORIGIN}/fixture-catalog.json",
            "source_kind": "ai_catalog_entry",
            "entries": entries,
        },
    )
    results = payload.get("results") if isinstance(payload, dict) else None
    if not isinstance(results, list) or len(results) != len(entries):
        raise SystemExit(
            f"seed ingestion did not record both entries: {payload}"
        )
    return [item for item in results if isinstance(item, dict)]


def _resource_id(results: list[dict], identifier: str) -> str:
    for item in results:
        if item.get("identifier") == identifier:
            return str(item.get("resource_id", ""))
    raise SystemExit(f"seed ingestion returned no id for {identifier}")


def main() -> int:
    workspace = Path(sys.argv[1]).expanduser()
    logion_home = Path(sys.argv[2]).expanduser()
    fixture_root = workspace / "ai-catalog-fixture"
    evidence = fixture_root / "evidence"
    evidence.mkdir(parents=True, exist_ok=True)

    _enable_flags()
    _start_fixture_server()

    api = base.Api(
        os.environ.get("PG_API_BASE_URL", "http://localhost:8000"),
        base._role_keys(),
    )
    results = _ingest_seed_entries(api)

    sys.stdout.write(
        json.dumps({
            "fixture_root": str(fixture_root),
            "logion_home": str(logion_home),
            "evidence_dir": str(evidence),
            "resource_id": _resource_id(results, fixture.LINTER),
            "catalog_url": f"{fixture.ORIGIN}/fixture-catalog.json",
            "finders_url": f"{fixture.ORIGIN}/agent-finders.json",
            # The type/source pair the filter proof narrows on. The
            # weather entry is a different type, so a filter that
            # excludes nothing is visible as a failure.
            "filter_type": "application/agent-skills+json",
            "filter_source": f"{fixture.ORIGIN}/fixture-catalog.json",
        })
        + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
