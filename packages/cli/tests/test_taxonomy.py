# SPDX-License-Identifier: MIT
"""Tests for CLI taxonomy helpers, --tag/--category search, and suggestions."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from cli._taxonomy import (
    CATEGORY_SLUGS,
    DEFAULT_CATEGORY,
    RESERVED_TAG_SLUGS,
    TAG_RE,
    TaxonomyValidationError,
    normalize_category,
    normalize_tag,
    normalize_tags,
    tag_search_tokens,
)
from cli.commands.courses._taxonomy_data import CATEGORY_KEYWORDS
from cli.commands.courses.parser import register as register_courses
from cli.commands.courses.taxonomy_suggest import suggest_taxonomy
from cli.commands.listings.parser import register as register_listings
from cli.main import main

# ---------------------------------------------------------------------------
# Taxonomy helper tests
# ---------------------------------------------------------------------------


def test_normalize_category_defaults_to_other() -> None:
    assert normalize_category(None) == DEFAULT_CATEGORY
    assert normalize_category("") == DEFAULT_CATEGORY


def test_normalize_category_accepts_known_slugs() -> None:
    assert normalize_category("devops") == "devops"
    assert normalize_category("Security") == "security"
    assert normalize_category("  writing  ") == "writing"


def test_normalize_category_rejects_unknown() -> None:
    with pytest.raises(TaxonomyValidationError, match="Unknown category"):
        normalize_category("foo")


def test_normalize_tag_converts_spaces_and_underscores() -> None:
    assert normalize_tag("pr review") == "pr-review"
    assert normalize_tag("ci_cd") == "ci-cd"
    assert normalize_tag("  Video Editing  ") == "video-editing"
    assert normalize_tag("multiple   spaces") == "multiple-spaces"


def test_normalize_tag_rejects_reserved() -> None:
    for reserved in RESERVED_TAG_SLUGS:
        with pytest.raises(TaxonomyValidationError, match="Reserved tag"):
            normalize_tag(reserved)


def test_normalize_tag_rejects_invalid() -> None:
    with pytest.raises(TaxonomyValidationError, match="Invalid tag"):
        normalize_tag("---")
    with pytest.raises(TaxonomyValidationError, match="Invalid tag"):
        normalize_tag("!@#$%")
    with pytest.raises(TaxonomyValidationError, match="Invalid tag"):
        normalize_tag("")


def test_normalize_tags_rejects_more_than_20() -> None:
    tags = [f"tag-{i}" for i in range(21)]
    with pytest.raises(TaxonomyValidationError, match="Too many tags"):
        normalize_tags(tags)


def test_normalize_tags_collapses_duplicates() -> None:
    result = normalize_tags(["python", "Python", "PYTHON"])
    assert result == ["python"]


def test_normalize_tags_preserves_order() -> None:
    result = normalize_tags(["zebra", "alpha", "beta"])
    assert result == ["zebra", "alpha", "beta"]


def test_tag_search_tokens_splits_hyphens() -> None:
    tokens = tag_search_tokens("pr-review")
    assert tokens == {"pr-review", "pr", "review"}


def test_tag_search_tokens_single_segment() -> None:
    tokens = tag_search_tokens("python")
    assert tokens == {"python"}


# ---------------------------------------------------------------------------
# Listings search --tag / --category tests
# ---------------------------------------------------------------------------


class FakeListingsResource:
    def __init__(self, items: list[dict[str, Any]] | None = None) -> None:
        self.items = items or []
        self.calls: list[dict[str, Any]] = []

    def search(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {"items": self.items, "next_cursor": None}


class FakeV1Namespace:
    def __init__(self, listings: FakeListingsResource) -> None:
        self.listings = listings


class FakeClient:
    def __init__(self, v1: FakeV1Namespace) -> None:
        self.v1 = v1

    def close(self) -> None:
        pass


def _patch_client(monkeypatch: pytest.MonkeyPatch, fake: FakeClient) -> None:
    monkeypatch.setattr("cli._context.LogionClient", lambda **_: fake)


def test_listings_search_accepts_repeat_tag_and_passes_comma_tags_to_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listings = FakeListingsResource([])
    fake = FakeClient(v1=FakeV1Namespace(listings=listings))
    _patch_client(monkeypatch, fake)

    code = main([
        "listings",
        "search",
        "--tag",
        "video",
        "--tag",
        "editing",
        "--json",
    ])
    assert code == 0
    call = listings.calls[-1]
    assert call["tags"] == "video,editing"


def test_listings_search_accepts_category(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listings = FakeListingsResource([])
    fake = FakeClient(v1=FakeV1Namespace(listings=listings))
    _patch_client(monkeypatch, fake)

    code = main([
        "listings",
        "search",
        "--category",
        "devops",
        "--tag",
        "terraform",
        "--json",
    ])
    assert code == 0
    call = listings.calls[-1]
    assert call["category"] == "devops"
    assert call["tags"] == "terraform"


def test_listings_search_rejects_tag_and_tags_together(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--tag and --tags are mutually exclusive."""
    listings = FakeListingsResource([])
    fake = FakeClient(v1=FakeV1Namespace(listings=listings))
    _patch_client(monkeypatch, fake)

    with pytest.raises(SystemExit) as exc_info:
        main([
            "listings",
            "search",
            "--tag",
            "video",
            "--tags",
            "video,editing",
            "--json",
        ])
    assert exc_info.value.code == 2


def test_listings_search_tags_legacy_still_works(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listings = FakeListingsResource([])
    fake = FakeClient(v1=FakeV1Namespace(listings=listings))
    _patch_client(monkeypatch, fake)

    code = main([
        "listings",
        "search",
        "--tags",
        "video,editing",
        "--json",
    ])
    assert code == 0
    call = listings.calls[-1]
    assert call["tags"] == "video,editing"


# ---------------------------------------------------------------------------
# Courses create/update --category tests
# ---------------------------------------------------------------------------


class FakeCoursesResource:
    def __init__(self) -> None:
        self.last_call: tuple[str, dict[str, Any]] = ("", {})

    def create(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("create", kwargs)
        return {"id": "c1", "title": kwargs.get("title", "")}

    def update(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("update", kwargs)
        return {"id": kwargs.get("course_id", ""), "updated": True}


class FakeCoursesV1:
    def __init__(self, courses: FakeCoursesResource) -> None:
        self.courses = courses


class FakeCoursesClient:
    def __init__(self, v1: FakeCoursesV1) -> None:
        self.v1 = v1

    def close(self) -> None:
        pass


def _patch_courses_client(
    monkeypatch: pytest.MonkeyPatch, fake: FakeCoursesClient
) -> None:
    monkeypatch.setattr("cli._context.LogionClient", lambda **_: fake)


def test_courses_create_accepts_category(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    courses = FakeCoursesResource()
    fake = FakeCoursesClient(v1=FakeCoursesV1(courses=courses))
    _patch_courses_client(monkeypatch, fake)
    code = main([
        "courses",
        "create",
        "--title",
        "Terraform Course",
        "--slug",
        "terraform",
        "--category",
        "devops",
        "--json",
    ])
    assert code == 0
    _method, kwargs = courses.last_call
    assert kwargs["category"] == "devops"


def test_courses_update_accepts_category(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    courses = FakeCoursesResource()
    fake = FakeCoursesClient(v1=FakeCoursesV1(courses=courses))
    _patch_courses_client(monkeypatch, fake)
    code = main([
        "courses",
        "update",
        "550e8400-e29b-41d4-a716-446655440000",
        "--category",
        "security",
        "--json",
    ])
    assert code == 0
    _method, kwargs = courses.last_call
    assert kwargs["category"] == "security"


# ---------------------------------------------------------------------------
# Taxonomy suggest tests
# ---------------------------------------------------------------------------


def test_taxonomy_suggest_from_skill_frontmatter(
    tmp_path: Path,
) -> None:
    """Suggestions are derived from SKILL.md frontmatter and body."""
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\n"
        "name: pr-review-bot\n"
        "description: Automated pull request review and code quality checks\n"
        "---\n\n"
        "# PR Review Bot\n\n"
        "Reviews GitHub pull requests for code quality.\n",
        encoding="utf-8",
    )
    result = suggest_taxonomy(tmp_path)
    assert "code-review" in result["category_suggestions"]
    assert "pr-review-bot" in result["tag_suggestions"]
    assert "SKILL.md" in result["source"]


def test_taxonomy_suggest_tokenizes_hyphenated_terms(
    tmp_path: Path,
) -> None:
    """Hyphenated SKILL.md terms produce segmented tag suggestions."""
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\n"
        "name: ci-cd-pipeline\n"
        "description: CI/CD pipeline automation with terraform\n"
        "---\n\n"
        "# CI/CD Pipeline\n",
        encoding="utf-8",
    )
    result = suggest_taxonomy(tmp_path)
    # "ci-cd-pipeline" should appear as a tag (from the hyphenated name).
    assert "ci-cd-pipeline" in result["tag_suggestions"]
    # "automation" or "devops" category should be suggested.
    assert any(
        cat in result["category_suggestions"]
        for cat in ("automation", "devops")
    )


def test_taxonomy_suggest_rejects_reserved_tags(
    tmp_path: Path,
) -> None:
    """Reserved labels found in text are reported in rejected_reserved."""
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\n"
        "name: official-verified-bot\n"
        "description: A bot with official and verified badges\n"
        "---\n\n"
        "# Official Verified Bot\n",
        encoding="utf-8",
    )
    result = suggest_taxonomy(tmp_path)
    # "official" and "verified" are reserved and should be rejected.
    assert "official" in result["rejected_reserved"]
    assert "verified" in result["rejected_reserved"]


def test_taxonomy_suggest_with_capabilities_yaml(
    tmp_path: Path,
) -> None:
    """capabilities.yaml summary is used as a text source."""
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\n"
        "name: security-audit\n"
        "description: Security auditing tool\n"
        "---\n\n"
        "# Security Audit\n",
        encoding="utf-8",
    )
    cap_dir = tmp_path / "course"
    cap_dir.mkdir()
    (cap_dir / "capabilities.yaml").write_text(
        "version: 1\n"
        "summary: Pentest and vulnerability scanning\n"
        "tools:\n  - bash\n  - python\n",
        encoding="utf-8",
    )
    result = suggest_taxonomy(tmp_path)
    assert "security" in result["category_suggestions"]
    assert "course/capabilities.yaml" in result["source"]


def test_taxonomy_suggest_defaults_to_other(
    tmp_path: Path,
) -> None:
    """No recognizable keywords yields 'other' category."""
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\n"
        "name: hello-world\n"
        "description: A simple greeting\n"
        "---\n\n"
        "# Hello World\n",
        encoding="utf-8",
    )
    result = suggest_taxonomy(tmp_path)
    assert result["category_suggestions"] == ["other"]


def test_taxonomy_suggest_cli_command(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """The CLI command produces JSON output."""
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\n"
        "name: terraform-deploy\n"
        "description: Deploy infrastructure with terraform\n"
        "---\n\n"
        "# Terraform Deploy\n",
        encoding="utf-8",
    )
    code = main([
        "courses",
        "taxonomy",
        "suggest",
        "--bundle-dir",
        str(tmp_path),
        "--json",
    ])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["kind"] == "logion.courses.taxonomy.suggest"
    assert "devops" in payload["data"]["category_suggestions"]


def test_taxonomy_suggest_text_mode_prints_output(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    """Without --json the handler prints human-readable lines to stdout."""
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\n"
        "name: terraform-deploy\n"
        "description: Deploy infrastructure with terraform\n"
        "---\n\n"
        "# Terraform Deploy\n",
        encoding="utf-8",
    )
    code = main([
        "courses",
        "taxonomy",
        "suggest",
        "--bundle-dir",
        str(tmp_path),
    ])
    assert code == 0
    captured = capsys.readouterr()
    assert captured.out.strip(), "text mode must produce stdout output"
    assert "category_suggestions:" in captured.out


# ---------------------------------------------------------------------------
# Deterministic category ordering
# ---------------------------------------------------------------------------


def test_taxonomy_suggest_category_order_matches_keyword_dict(
    tmp_path: Path,
) -> None:
    """Category order follows CATEGORY_KEYWORDS keys, not frozenset."""
    # Tokens that match several categories so ordering is observable.
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\n"
        "name: multi-tool\n"
        "description: security audit and data pipeline with video editing\n"
        "---\n\n"
        "# Multi Tool\n",
        encoding="utf-8",
    )
    result = suggest_taxonomy(tmp_path)
    cats = result["category_suggestions"]
    keyword_order = [c for c in CATEGORY_KEYWORDS if c in cats]
    assert cats == keyword_order


def test_taxonomy_suggest_category_order_is_hash_seed_independent(
    tmp_path: Path,
) -> None:
    """Running suggest_taxonomy under different PYTHONHASHSEED values
    must produce the same category order."""
    skill = tmp_path / "SKILL.md"
    skill.write_text(
        "---\n"
        "name: multi-tool\n"
        "description: security audit and data pipeline with video editing\n"
        "---\n\n"
        "# Multi Tool\n",
        encoding="utf-8",
    )
    bundle = str(tmp_path)

    snippet = (
        "from pathlib import Path\n"
        "from cli.commands.courses.taxonomy_suggest import suggest_taxonomy\n"
        f"r = suggest_taxonomy(Path({bundle!r}))\n"
        "print(','.join(r['category_suggestions']))\n"
    )

    repo_root = Path(__file__).resolve().parents[3]
    results: list[str] = []
    for seed in (0, 1, 2, 3, 4):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = str(seed)
        env["PYTHONPATH"] = os.pathsep.join([
            str(repo_root / "packages" / "cli"),
            str(repo_root / "packages" / "client" / "src"),
        ])
        proc = subprocess.run(
            [sys.executable, "-c", snippet],
            capture_output=True,
            text=True,
            cwd=str(repo_root),
            env=env,
        )
        assert proc.returncode == 0, proc.stderr
        results.append(proc.stdout.strip())
    assert len(set(results)) == 1, f"non-deterministic order: {results}"


# ---------------------------------------------------------------------------
# Golden constants test pinning CLI taxonomy against backend source-of-truth
# ---------------------------------------------------------------------------


EXPECTED_CATEGORY_SLUGS = frozenset({
    "automation",
    "code-review",
    "data",
    "devops",
    "documentation",
    "finance",
    "marketing",
    "media",
    "productivity",
    "research",
    "security",
    "testing",
    "writing",
    "other",
})
EXPECTED_RESERVED_TAG_SLUGS = frozenset({
    "official",
    "verified",
    "trusted",
    "featured",
    "logion",
    "admin",
    "staff",
    "platform",
    "security-audited",
})
EXPECTED_TAG_RE_PATTERN = r"^[a-z0-9][a-z0-9-]{0,63}$"


def test_taxonomy_constants_pin_category_slugs() -> None:
    """CATEGORY_SLUGS must match the shared source-of-truth set exactly."""
    assert CATEGORY_SLUGS == EXPECTED_CATEGORY_SLUGS


def test_taxonomy_constants_pin_reserved_tag_slugs() -> None:
    """RESERVED_TAG_SLUGS must match the shared source-of-truth set exactly."""
    assert RESERVED_TAG_SLUGS == EXPECTED_RESERVED_TAG_SLUGS


def test_taxonomy_constants_pin_tag_re_pattern() -> None:
    """TAG_RE pattern must match the shared source-of-truth pattern."""
    assert TAG_RE.pattern == EXPECTED_TAG_RE_PATTERN


# ---------------------------------------------------------------------------
# Parser registration smoke tests
# ---------------------------------------------------------------------------


def test_listings_parser_has_tag_and_category() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    register_listings(subparsers)
    args = parser.parse_args([
        "listings",
        "search",
        "--category",
        "devops",
        "--tag",
        "terraform",
    ])
    assert args.category == "devops"
    assert args.tag_filters == ["terraform"]


def test_courses_parser_has_category_create() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    register_courses(subparsers)
    args = parser.parse_args([
        "courses",
        "create",
        "--title",
        "T",
        "--slug",
        "t",
        "--category",
        "writing",
    ])
    assert args.category == "writing"
