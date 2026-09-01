# SPDX-License-Identifier: MIT
"""Tests for the generated documentation site at /docs.

The point of generating this reference is that it cannot describe an API or a
CLI that does not exist. These tests hold that property: the artifact must be
current (proven by actually running the generator), the cross-links between the
two references must resolve, and every page must answer for both readers.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from landing.docs_site import DocsSite, anchor_for, load_docs, render_html
from landing.main import app, sitemap_paths

REPO_ROOT = Path(__file__).resolve().parents[3]
ARTIFACT_PATH = (
    REPO_ROOT / "packages" / "landing" / "landing" / "content" / "docs.json"
)

client = TestClient(app)
docs = load_docs()


# --------------------------------------------------------------------------
# the artifact is current, and staleness is detectable
# --------------------------------------------------------------------------


def test_docs_artifact_is_current() -> None:
    """The committed artifact matches what the generator produces now.

    This is the whole guarantee. If the OpenAPI contract syncs a new endpoint
    or someone adds a CLI flag, the documentation silently describes the old
    surface until this fails.
    """
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "gen_docs.py"),
            "--check",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        "docs artifact is stale. Run `make docs-generate` and commit "
        f"the result.\n{result.stdout}\n{result.stderr}"
    )


def test_stale_artifact_fails_the_check(tmp_path: Path) -> None:
    """The freshness check must actually be able to fail.

    A check that cannot go red is decoration. This mutates a copy of the
    artifact and proves the comparison notices.
    """
    original = ARTIFACT_PATH.read_text(encoding="utf-8")
    (tmp_path / "docs.json").write_text(original, encoding="utf-8")
    try:
        data = json.loads(original)
        data["source"]["operations"] = -1
        ARTIFACT_PATH.write_text(
            json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False)
            + "\n",
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "gen_docs.py"),
                "--check",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        assert "stale" in result.stderr
    finally:
        ARTIFACT_PATH.write_text(original, encoding="utf-8")


@pytest.mark.parametrize(
    "env",
    [
        pytest.param({"LOGION_ENABLE_ADMIN": "1"}, id="admin-on"),
        pytest.param({"LOGION_ENABLE_ADMIN": "0"}, id="admin-off"),
        pytest.param({}, id="admin-unset"),
    ],
)
def test_generation_ignores_the_ambient_environment(
    env: dict[str, str], tmp_path: Path
) -> None:
    """The artifact must be a function of the repository, nothing else.

    Regression: `logion admin` is gated on LOGION_ENABLE_ADMIN, so argparse
    builds a 13-command subtree or a single hidden stub depending on a
    variable that happened to be set in one maintainer's shell and not in CI.
    The committed artifact was generated with it set and the check failed
    everywhere else. A generator whose output depends on who ran it makes the
    freshness check worse than useless — it goes red for the wrong reason.
    """
    child_env = {
        key: value
        for key, value in os.environ.items()
        if key != "LOGION_ENABLE_ADMIN"
    }
    child_env.update(env)
    output = tmp_path / "docs.json"
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "gen_docs.py"),
            "--check",
        ],
        cwd=REPO_ROOT,
        env=child_env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"generation depends on the environment {env}:\n"
        f"{result.stdout}\n{result.stderr}"
    )
    assert not output.exists()


def test_renderer_refuses_an_artifact_it_does_not_understand() -> None:
    """A future artifact shape must be rejected, not partially rendered."""
    with pytest.raises(ValueError, match="not supported"):
        DocsSite({"artifact_version": 99, "pages": {}, "sections": []})


# --------------------------------------------------------------------------
# coverage: the reference describes the whole surface
# --------------------------------------------------------------------------


def test_every_contract_tag_has_a_page() -> None:
    spec = json.loads(
        (REPO_ROOT / "contracts" / "openapi" / "v1.json").read_text("utf-8")
    )
    tags = {
        tag
        for methods in spec["paths"].values()
        for method, operation in methods.items()
        if method in ("get", "post", "put", "patch", "delete")
        for tag in (operation.get("tags") or ["general"])
    }
    missing = [
        tag for tag in tags if f"api/{tag.replace('_', '-')}" not in docs
    ]
    assert not missing, f"contract tags with no documentation page: {missing}"


def test_every_operation_id_is_documented() -> None:
    spec = json.loads(
        (REPO_ROOT / "contracts" / "openapi" / "v1.json").read_text("utf-8")
    )
    operation_ids = {
        operation["operationId"]
        for methods in spec["paths"].values()
        for method, operation in methods.items()
        if method in ("get", "post", "put", "patch", "delete")
        and operation.get("operationId")
    }
    documented = "\n".join(page.body for page in docs.pages)
    missing = sorted(op for op in operation_ids if f"`{op}`" not in documented)
    assert not missing, f"operations absent from the reference: {missing}"


def test_every_cli_group_has_a_page() -> None:
    from cli._parser import build_parser

    # argparse exposes no public reader for its actions.
    groups = {
        name
        for action in build_parser()._actions
        if hasattr(action, "choices") and action.choices
        for name in action.choices
    }
    missing = [group for group in groups if f"cli/{group}" not in docs]
    assert not missing, f"CLI groups with no documentation page: {missing}"


# --------------------------------------------------------------------------
# the cross-link between the two references resolves
# --------------------------------------------------------------------------


_DOC_LINK = re.compile(r"\]\(/docs/([a-z0-9/_-]+)(#[a-z0-9-]+)?\)")


def test_internal_doc_links_resolve() -> None:
    """Every /docs link points at a page that exists, at an anchor that exists.

    A generated cross-reference whose links 404 is worse than none: it is
    confidently wrong. The anchors are generated on one side and rendered on
    the other, so this is where the two definitions are proven to agree.
    """
    broken: list[str] = []
    for page in docs.pages:
        for slug, anchor in _DOC_LINK.findall(page.body):
            target = docs.get(slug)
            if target is None:
                broken.append(f"{page.slug} -> /docs/{slug} (no such page)")
                continue
            if not anchor:
                continue
            anchors = {
                anchor_for(text)
                for text in re.findall(r"^#{2,3} (.+)$", target.body, re.M)
            }
            if anchor.lstrip("#") not in anchors:
                broken.append(f"{page.slug} -> /docs/{slug}{anchor}")
    assert not broken, "broken documentation links:\n" + "\n".join(broken)


def test_cross_links_are_bidirectional() -> None:
    """If a CLI page claims to call an operation, that operation links back."""
    mismatches: list[str] = []
    for page in docs.pages:
        if not page.slug.startswith("cli/"):
            continue
        for slug, anchor in _DOC_LINK.findall(page.body):
            if not slug.startswith("api/"):
                continue
            target = docs.get(slug)
            assert target is not None
            if f"](/docs/{page.slug}#" not in target.body:
                mismatches.append(f"{page.slug} -> {slug}{anchor}")
    assert not mismatches, (
        "CLI pages linking to API pages that do not link back:\n"
        + "\n".join(mismatches)
    )


def test_a_known_command_links_to_its_endpoint() -> None:
    """Anchor case: listings search is the simplest full chain in the CLI."""
    cli_page = docs.get("cli/listings")
    api_page = docs.get("api/listings")
    assert cli_page is not None
    assert api_page is not None
    assert "/docs/api/listings#search-listings" in cli_page.body
    assert "/docs/cli/listings#logion-listings-search" in api_page.body


# --------------------------------------------------------------------------
# routes
# --------------------------------------------------------------------------


def test_docs_index_renders() -> None:
    response = client.get("/docs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "API Reference" in response.text
    assert "CLI Reference" in response.text


def test_every_page_answers_html_and_markdown() -> None:
    """One URL, two readers — the same rule the rest of the site follows."""
    for page in docs.pages:
        html = client.get(page.url)
        assert html.status_code == 200, page.url
        assert "text/html" in html.headers["content-type"], page.url

        negotiated = client.get(page.url, headers={"Accept": "text/markdown"})
        assert negotiated.status_code == 200, page.url
        assert "text/markdown" in negotiated.headers["content-type"], page.url

        explicit = client.get(page.markdown_url)
        assert explicit.status_code == 200, page.markdown_url
        assert explicit.text == page.body


def test_unknown_page_is_404() -> None:
    assert client.get("/docs/api/does-not-exist").status_code == 404


def test_path_traversal_is_rejected() -> None:
    for hostile in ("/docs/../../etc/passwd", "/docs/..%2f..%2fetc%2fpasswd"):
        assert client.get(hostile).status_code in (404, 400)


def test_docs_llms_txt_lists_every_page() -> None:
    response = client.get("/docs/llms.txt")
    assert response.status_code == 200
    assert "text/plain" in response.headers["content-type"]
    for section in docs.sections:
        for entry in section["pages"]:
            assert f"/docs/{entry['slug']}.md" in response.text


def test_docs_are_in_the_sitemap() -> None:
    paths = sitemap_paths()
    assert "/docs" in paths
    assert "/docs/api/overview" in paths
    assert "/docs/cli/overview" in paths


def test_sidebar_marks_the_current_page() -> None:
    response = client.get("/docs/api/listings")
    assert 'aria-current="page"' in response.text


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------


def test_tables_render() -> None:
    """Reference pages are mostly tables; CommonMark has none by default."""
    assert "<table>" in render_html("| a | b |\n| --- | --- |\n| 1 | 2 |\n")


def test_headings_carry_their_anchors() -> None:
    html = render_html("## Search listings\n\ntext\n")
    assert 'id="search-listings"' in html


def test_raw_html_in_a_page_is_not_executed() -> None:
    """Guides are hand-written and flow through the same renderer.

    The rendered body is wrapped in ``Markup`` before it reaches the template,
    so bandit's B704 is suppressed there on the strength of this and the next
    test. Both need to keep holding for that suppression to stay honest.
    """
    html = render_html("<script>alert(1)</script>\n")
    assert "<script>" not in html


@pytest.mark.parametrize(
    "scheme",
    [
        "javascript:alert(1)",
        "vbscript:alert(1)",
        "file:///etc/passwd",
        "data:text/html,<b>",
    ],
)
def test_dangerous_link_schemes_never_become_hrefs(scheme: str) -> None:
    """markdown-it's link validator must keep rejecting these.

    It rejects the link rather than sanitising it, so the URL survives as
    escaped body text. What must never happen is it reaching an ``href``.
    """
    html = render_html(f"[click]({scheme})\n")
    assert "<a " not in html
    assert "href" not in html


def test_ordinary_links_still_render() -> None:
    """The guard above is only meaningful if normal links work."""
    html = render_html("[docs](/docs/api/overview)\n")
    assert '<a href="/docs/api/overview">docs</a>' in html


def test_generated_pages_declare_their_provenance() -> None:
    """A reader must be able to tell generated reference from written prose."""
    response = client.get("/docs/api/listings")
    assert "Generated from" in response.text
    assert "how-these-docs-are-built" in response.text
