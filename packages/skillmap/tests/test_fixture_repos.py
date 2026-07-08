"""Real-repo inference fixtures, pinned to immutable commit SHAs.

These are network-gated: they fetch each repo's tarball via ``gh`` at the
pinned SHA and assert the inferred component count, source, and a subset of
review flags. Because they hit the network (and one repo is large), they
run only when ``LOGION_SKILLMAP_NET_FIXTURES=1`` is set *and* ``gh`` is
authenticated — otherwise they skip. Pins were recorded 2026-07-07; refresh
by re-resolving each repo's default-branch SHA and re-running inference.
"""

from __future__ import annotations

import os

import pytest
from _github_fixture import GitHubUnavailable, fetch_repo, gh_available

from logion_skillmap.inference import _EXCLUDED_SEGMENTS, infer

# repo -> pinned (sha, components, source, must-have flag subset)
FIXTURES = {
    "mattpocock/skills": {
        "sha": "8515a080a74dbcf5019a1a78efc24b5fcafb36b8",  # pragma: allowlist secret
        "components": 34,
        "source": "skill_scan",
        "flags": {
            "skillmap_component_cap_exceeded",
            "skillmap_excluded_segment",
        },
    },
    "MiniMax-AI/skills": {
        "sha": "60aaae52bb2af8162732751a4332f62a5fef518b",  # pragma: allowlist secret
        "components": 23,
        "source": "skill_scan",
        "flags": {"ambiguous_primary_tree"},
    },
    "andrewyng/context-hub": {
        "sha": "67dcbeb2eb42c808549f08397920ad58be7c2206",  # pragma: allowlist secret
        "components": 10,
        "source": "skill_scan",
        "flags": {"skillmap_excluded_segment"},
    },
    "uphiago/recon-skills": {
        "sha": "9df9fc404174a5f7cefad9aacee1347815e252c8",  # pragma: allowlist secret
        "components": 170,
        "source": "skill_scan",
        "flags": {"no_license", "skillmap_component_cap_exceeded"},
    },
    "zarazhangrui/frontend-slides": {
        "sha": "9906a34d640d2111f724544cbc50f7f130569ae1",  # pragma: allowlist secret
        "components": 1,
        "source": "skill_scan",
        "flags": set(),
    },
    "affaan-m/ECC": {
        "sha": "4130457d674d2180c5af2c5f634f3cae4cbc6c4f",  # pragma: allowlist secret
        "components": 883,
        "source": "skill_scan",
        "flags": {"skillmap_component_cap_exceeded", "ambiguous_primary_tree"},
    },
    "ComposioHQ/awesome-claude-skills": {
        "sha": "92568c1edaff1bde5371154f036d959346c145a8",  # pragma: allowlist secret
        "components": 864,
        "source": "skill_scan",
        "flags": {"no_license", "skillmap_component_cap_exceeded"},
    },
}

_GATE = os.getenv("LOGION_SKILLMAP_NET_FIXTURES") == "1"


def _has_excluded_segment(root: str) -> bool:
    return bool(_EXCLUDED_SEGMENTS.intersection(root.split("/")))


@pytest.mark.skipif(
    not _GATE,
    reason="network fixtures gated behind LOGION_SKILLMAP_NET_FIXTURES=1",
)
@pytest.mark.parametrize("repo", list(FIXTURES))
def test_real_repo_inference(repo: str) -> None:
    if not gh_available():
        pytest.skip(reason="gh CLI unavailable/unauthenticated for fixtures")

    pin = FIXTURES[repo]
    try:
        tree, read_blob = fetch_repo(repo, pin["sha"])
    except GitHubUnavailable as exc:
        pytest.skip(reason=f"could not fetch {repo}: {exc}")

    result = infer(tree, read_blob)
    got_flags = {f.code for f in result.needs_review}

    assert result.source == pin["source"], repo
    assert len(result.components) == pin["components"], (
        f"{repo}: expected {pin['components']} components, "
        f"got {len(result.components)}"
    )
    assert pin["flags"].issubset(got_flags), (
        f"{repo}: missing flags {pin['flags'] - got_flags}"
    )
    # Exclusion pass must hold on real trees: no canonical component root
    # may contain an excluded path segment (test/fixtures/deprecated/…).
    offenders = [
        c.root for c in result.components if _has_excluded_segment(c.root)
    ]
    assert not offenders, f"{repo}: excluded-segment roots leaked: {offenders}"
