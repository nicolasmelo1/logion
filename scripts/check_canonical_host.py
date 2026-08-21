#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check that the canonical host serves itself instead of redirecting away.

Every offline check in this repo reads ``canonical_base`` from site.yaml and
trusts it. Nothing ever asked the host whether it agrees, and for a long time
it did not: ``canonical_base`` named the apex while the apex answered
``308 -> www`` on every path, so third-party indexes recorded ``www`` no matter
what the pages declared. ``canonical_base`` now names ``www``, matching the
deployment; this check is what keeps the two from drifting apart again, in
either direction.

The drift is invisible to every other checker by construction: a unit test, a
link checker and a sitemap validator all follow the redirect and see 200. Only
an unfollowed request shows it, which is what this does.

Network-dependent, so it is deliberately outside ``make ci-checks``: CI must
not go red on a DNS blip. Run it after any DNS, domain, or proxy change.
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
SITE_YAML = ROOT / "packages" / "landing" / "landing" / "content" / "site.yaml"
CANONICAL_BASE_RE = re.compile(
    r"^\s*canonical_base:\s*(?P<url>https://\S+)\s*$", re.MULTILINE
)
CANONICAL_LINK_RE = re.compile(
    r"""<link[^>]*\brel=["']canonical["'][^>]*\bhref=["'](?P<href>[^"']+)""",
    re.IGNORECASE,
)
# One page plus one non-HTML asset. A domain-level redirect hits every path,
# but a rule scoped to a path prefix would only show on the second.
PROBE_PATHS = ("/", "/llms.txt")
TIMEOUT_SECONDS = 15.0
USER_AGENT = "logion-canonical-host-check"


@dataclass(frozen=True)
class Probe:
    """What one unfollowed request to a canonical URL returned."""

    url: str
    status: int
    location: str | None
    canonical_href: str | None


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    """Surface a 3xx as an error instead of quietly following it.

    Following the redirect is exactly the behaviour that hid this problem
    from every other checker.
    """

    # urllib calls this positionally as
    # (req, fp, code, msg, headers, newurl); the override ignores all of
    # them, so *args says that more honestly than six unused names.
    def redirect_request(self, *_args: object) -> None:
        return None


def read_canonical_base(site_yaml: Path = SITE_YAML) -> str:
    """Return ``seo.canonical_base`` as committed in site.yaml."""
    match = CANONICAL_BASE_RE.search(site_yaml.read_text(encoding="utf-8"))
    if match is None:
        raise SystemExit(f"no canonical_base found in {site_yaml}")
    return match.group("url").rstrip("/")


def probe(url: str) -> Probe:
    """Request *url* once, without following redirects."""
    opener = urllib.request.build_opener(_NoRedirects)
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "*/*"}
    )
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read(200_000).decode("utf-8", errors="replace")
            link = CANONICAL_LINK_RE.search(body)
            return Probe(
                url=url,
                status=response.status,
                location=None,
                canonical_href=link.group("href") if link else None,
            )
    except urllib.error.HTTPError as exc:
        return Probe(
            url=url,
            status=exc.code,
            location=exc.headers.get("location"),
            canonical_href=None,
        )
    except (urllib.error.URLError, TimeoutError) as exc:
        raise SystemExit(f"{url}: unreachable ({exc})") from exc


def findings(base: str, probes: list[Probe]) -> list[str]:
    """Return one human-readable line per problem, empty when healthy."""
    problems: list[str] = []
    base_host = urlsplit(base).netloc
    for result in probes:
        if 300 <= result.status < 400:
            target = result.location or "(no Location header)"
            problems.append(
                f"{result.url} -> {result.status} -> {target}\n"
                "    The declared canonical redirects away from itself. "
                "Indexes and\n"
                "    crawlers will record the redirect target, not this URL."
            )
            continue
        if result.status != 200:
            problems.append(f"{result.url} -> {result.status} (expected 200)")
            continue
        href = result.canonical_href
        if href is None:
            continue
        served_host = urlsplit(href).netloc
        if served_host != base_host:
            problems.append(
                f'{result.url} serves rel="canonical" -> {href}\n'
                f"    Its host ({served_host}) is not the canonical host "
                f"({base_host})."
            )
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        help="override the canonical base (defaults to site.yaml)",
    )
    args = parser.parse_args(argv)

    base = (args.base or read_canonical_base()).rstrip("/")
    results = [probe(f"{base}{path}") for path in PROBE_PATHS]
    problems = findings(base, results)

    if not problems:
        sys.stdout.write(f"check_canonical_host: ok ({base} serves itself).\n")
        return 0

    sys.stdout.write("check_canonical_host: canonical host disagrees:\n")
    for problem in problems:
        sys.stdout.write(f"  {problem}\n")
    sys.stdout.write(
        "\nEither point the redirect at the canonical host, or change "
        "seo.canonical_base\nin packages/landing/landing/content/site.yaml "
        "to the host that actually serves.\n"
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
