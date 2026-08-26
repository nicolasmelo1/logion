#!/usr/bin/env python3
"""A stand-in ecosystem: one connector directory, two finders, one catalog.

The scenario needs a world outside the node under test -- somewhere the
operator can sync a pinned directory from, query finders in, and crawl a
catalog that was not produced by the code being proved. Pointing all of
that at the node's own endpoints would make the run a mirror: every
claim would hold because one implementation agreed with itself.

The catalog deliberately contains an entry that violates the spec's
value-or-reference rule. A crawl that only ever sees well-formed input
cannot demonstrate that malformed input is quarantined, and the phase
gate asks exactly that.
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = 18770
ORIGIN = f"http://127.0.0.1:{PORT}"

LINTER = "urn:air:fixture-node:skill:linter"
WEATHER = "urn:air:fixture-node:mcp:weather"

#: One valid entry, one of a different type so a type filter has
#: something to exclude, and one that sets both `url` and `data`.
CATALOG: dict = {
    "specVersion": "1.0",
    "host": {
        "displayName": "Fixture Ecosystem",
        "identifier": "urn:air:fixture-node",
    },
    "entries": [
        {
            "identifier": LINTER,
            "type": "application/agent-skills+json",
            "url": f"{ORIGIN}/artifacts/linter.json",
            "displayName": "Fixture Linter",
            "description": "Lints fixtures. Exists to be discovered.",
            "tags": ["fixture", "linting"],
            "publisher": {
                "identifier": "urn:air:fixture-node:publisher",
                "displayName": "fixture-node",
            },
        },
        {
            "identifier": WEATHER,
            "type": "application/mcp-server-card+json",
            "url": f"{ORIGIN}/artifacts/weather.json",
            "displayName": "Fixture Weather",
            "description": "A second type, so a filter can narrow.",
            "tags": ["fixture", "weather"],
            "publisher": {
                "identifier": "urn:air:fixture-node:publisher",
                "displayName": "fixture-node",
            },
        },
        {
            "identifier": "urn:air:fixture-node:skill:broken",
            "type": "application/agent-skills+json",
            "url": f"{ORIGIN}/artifacts/broken.json",
            "data": {"inline": "and a url too"},
            "displayName": "Fixture Broken",
        },
    ],
}

FINDERS = {
    "finders": [
        {
            "id": "fixture-finder-a",
            "name": "Fixture Finder A",
            "description": "Returns the linter and a referral.",
            "search": f"{ORIGIN}/finder-a/search",
        },
        {
            "id": "fixture-finder-b",
            "name": "Fixture Finder B",
            "description": "Returns the same linter, so dedup is exercised.",
            "search": f"{ORIGIN}/finder-b/search",
        },
    ]
}

FINDER_A = {
    "results": [
        {
            "identifier": LINTER,
            "type": "application/agent-skills+json",
            "url": f"{ORIGIN}/artifacts/linter.json",
            "displayName": "Fixture Linter",
            "score": 92,
            "source": f"{ORIGIN}/finder-a/search",
        }
    ],
    "referrals": [
        {
            "identifier": "urn:air:fixture-node:registry:partner",
            "displayName": "Partner Registry",
            "type": "application/ai-registry+json",
            "url": f"{ORIGIN}/partner/search",
        }
    ],
}

#: The same identifier as finder A returns, from a different finder. Two
#: finders naming one artifact is the normal case, not an error, and the
#: run has to end with one resource rather than two.
#:
#: The malformed input lives in the catalog rather than here on purpose.
#: The ARD response codec decodes a search response as a unit, so one bad
#: record fails the whole response and the finder returns nothing -- which
#: exercises a finder being unreachable, not a record being quarantined.
#: Quarantine is a crawl-side behaviour and is proved where it exists.
FINDER_B = {
    "results": [
        {
            "identifier": LINTER,
            "type": "application/agent-skills+json",
            "url": f"{ORIGIN}/artifacts/linter.json",
            "displayName": "Fixture Linter",
            "score": 71,
            "source": f"{ORIGIN}/finder-b/search",
        }
    ],
    "referrals": [],
}

ARTIFACTS = {
    "/artifacts/linter.json": {"name": "fixture-linter", "version": "1.0.0"},
    "/artifacts/weather.json": {"name": "fixture-weather", "version": "1.0.0"},
    "/artifacts/broken.json": {"name": "fixture-broken"},
}

ROUTES = {
    "/agent-finders.json": FINDERS,
    "/fixture-catalog.json": CATALOG,
    **ARTIFACTS,
}


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        payload = ROUTES.get(self.path)
        if payload is None:
            self.send_response(404)
            self.end_headers()
            return
        self._respond(payload)

    def do_POST(self) -> None:
        payload = {
            "/finder-a/search": FINDER_A,
            "/finder-b/search": FINDER_B,
        }.get(self.path)
        if payload is None:
            self.send_response(404)
            self.end_headers()
            return
        length = min(int(self.headers.get("Content-Length", "0")), 65536)
        self.rfile.read(length)
        self._respond(payload)

    def _respond(self, payload: object) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        return


if __name__ == "__main__":
    try:
        ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()
    except OSError as exc:
        # Already bound: a previous run's server is still serving the
        # same fixtures, which is the desired state, not an error.
        sys.stderr.write(f"fixture server not started: {exc}\n")
        raise SystemExit(0) from exc
