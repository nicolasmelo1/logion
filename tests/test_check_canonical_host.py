# SPDX-License-Identifier: MIT
"""Tests for scripts/check_canonical_host.py.

The script's only network-free part is its verdict, so that is what is tested
here: given what a host returned, does the check call it healthy? The probing
itself needs the live internet and stays out of ``make test``.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "check_canonical_host.py"

_spec = importlib.util.spec_from_file_location("check_canonical_host", SCRIPT)
assert _spec is not None
assert _spec.loader is not None
check_canonical_host = importlib.util.module_from_spec(_spec)
sys.modules["check_canonical_host"] = check_canonical_host
_spec.loader.exec_module(check_canonical_host)

Probe = check_canonical_host.Probe
findings = check_canonical_host.findings

BASE = "https://logion.sh"


def _ok(path: str = "/", canonical: str | None = None) -> object:
    return Probe(
        url=f"{BASE}{path}",
        status=200,
        location=None,
        canonical_href=canonical,
    )


def test_host_serving_itself_is_healthy() -> None:
    probes = [_ok("/", f"{BASE}/"), _ok("/llms.txt")]
    assert findings(BASE, probes) == []


def test_canonical_redirecting_away_is_reported() -> None:
    # The real failure: the apex answered 308 -> www on every path while the
    # pages kept declaring the apex as canonical.
    probes = [
        Probe(
            url=f"{BASE}/",
            status=308,
            location="https://www.logion.sh/",
            canonical_href=None,
        )
    ]
    problems = findings(BASE, probes)
    assert len(problems) == 1
    assert "308" in problems[0]
    assert "https://www.logion.sh/" in problems[0]
    assert "redirects away from itself" in problems[0]


@pytest.mark.parametrize("status", [301, 302, 307, 308])
def test_every_redirect_class_is_caught(status: int) -> None:
    probes = [
        Probe(
            url=f"{BASE}/",
            status=status,
            location="https://elsewhere.example/",
            canonical_href=None,
        )
    ]
    assert findings(BASE, probes)


def test_missing_location_header_still_reports() -> None:
    probes = [
        Probe(url=f"{BASE}/", status=308, location=None, canonical_href=None)
    ]
    assert "(no Location header)" in findings(BASE, probes)[0]


def test_served_canonical_pointing_at_another_host_is_reported() -> None:
    # The inverse drift: the host serves fine, but the page it serves names a
    # different host as canonical — so the two disagree either way round.
    probes = [_ok("/", "https://www.logion.sh/")]
    problems = findings(BASE, probes)
    assert len(problems) == 1
    assert "is not the canonical host" in problems[0]


def test_non_200_is_reported() -> None:
    probes = [
        Probe(url=f"{BASE}/", status=503, location=None, canonical_href=None)
    ]
    assert "503" in findings(BASE, probes)[0]


def test_page_without_a_canonical_link_is_not_a_finding() -> None:
    # Non-HTML probes (llms.txt) carry no rel="canonical"; absence is not
    # disagreement, or every text asset would fail the check.
    assert findings(BASE, [_ok("/llms.txt", None)]) == []


def test_canonical_base_is_read_from_site_yaml() -> None:
    base = check_canonical_host.read_canonical_base()
    assert base.startswith("https://")
    assert not base.endswith("/")
