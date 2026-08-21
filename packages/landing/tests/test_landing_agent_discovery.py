# SPDX-License-Identifier: MIT
"""Tests for the machine-readable discovery surfaces.

These are the files an agent reads *before* it reads a page: the ARD catalog,
the Agent Skills index, the ``.md`` alternates, and the HEAD/404 behaviour that
decides whether a crawler gets anywhere at all. Every assertion here guards a
promise made to a non-human client, so a regression is silent from a browser.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

LANDING_DIR = Path(__file__).resolve().parents[1]
if str(LANDING_DIR) not in sys.path:
    sys.path.insert(0, str(LANDING_DIR))

from landing.main import (  # noqa: E402
    AGENT_SKILLS_SCHEMA,
    AI_CATALOG_MEDIA_TYPE,
    API_BASE,
    CONTENT_DIR,
    MARKDOWN_PAGES,
    app,
)

client = TestClient(app)

AI_CATALOG_PATH = "/.well-known/ai-catalog.json"
AGENT_SKILLS_PATH = "/.well-known/agent-skills/index.json"
SKILL_PATH = "/.well-known/agent-skills/logion/SKILL.md"


# ── ai-catalog.json (Agentic Resource Discovery) ──────────────────


def test_ai_catalog_is_served_with_its_registered_media_type() -> None:
    response = client.get(AI_CATALOG_PATH)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith(AI_CATALOG_MEDIA_TYPE)


def test_ai_catalog_meets_level_2_conformance() -> None:
    # Level 1 is specVersion + entries; Level 2 adds a host object and being
    # served at the well-known URI. Below Level 2 a client cannot attribute
    # the catalog to an operator.
    catalog = client.get(AI_CATALOG_PATH).json()
    assert catalog["specVersion"]
    assert catalog["host"]["displayName"]
    assert catalog["host"]["identifier"]
    assert catalog["entries"]


def test_ai_catalog_entries_carry_the_required_members() -> None:
    for entry in client.get(AI_CATALOG_PATH).json()["entries"]:
        assert entry["identifier"].startswith("urn:air:logion.sh:"), entry
        assert entry["type"], entry
        # Exactly one of url/data, and we always publish url.
        assert entry["url"].startswith("https://"), entry
        assert "data" not in entry, entry


def test_ai_catalog_declares_no_artifact_it_cannot_serve() -> None:
    # A catalog entry pointing at nothing is worse for an agent than no
    # catalog: it burns a fetch and teaches it to distrust the index. Entries
    # on our own host must resolve here; off-host ones are asserted by URL.
    for entry in client.get(AI_CATALOG_PATH).json()["entries"]:
        url = entry["url"]
        if url.startswith("https://www.logion.sh/"):
            path = url[len("https://www.logion.sh") :]
            assert client.get(path).status_code == 200, url
        else:
            assert url == f"{API_BASE}/openapi.json", url


def test_ai_catalog_does_not_claim_an_mcp_server() -> None:
    # Logion deliberately ships no MCP server (see the FAQ). Declaring one
    # here to satisfy a scanner would be a discoverable dead end.
    types = {e["type"] for e in client.get(AI_CATALOG_PATH).json()["entries"]}
    assert not any("mcp" in t for t in types), types


def test_ai_catalog_is_advertised_by_link_relation() -> None:
    # Step 2 of the spec's agent-driven discovery procedure: an agent that
    # fetched a page should find the catalog without guessing the path.
    html = client.get("/").text
    assert 'rel="ai-catalog"' in html
    assert f'href="https://www.logion.sh{AI_CATALOG_PATH}"' in html
    assert f'type="{AI_CATALOG_MEDIA_TYPE}"' in html


# ── agent-skills discovery ────────────────────────────────────────


def test_agent_skills_index_declares_the_discovery_schema() -> None:
    index = client.get(AGENT_SKILLS_PATH).json()
    assert index["$schema"] == AGENT_SKILLS_SCHEMA
    assert index["skills"]


def test_agent_skills_entries_carry_the_required_fields() -> None:
    for skill in client.get(AGENT_SKILLS_PATH).json()["skills"]:
        assert skill["name"]
        assert skill["type"] in {"skill-md", "archive"}
        assert skill["description"]
        assert skill["url"].startswith("https://www.logion.sh/")
        assert skill["digest"].startswith("sha256:")


def test_agent_skills_digest_matches_the_bytes_we_serve() -> None:
    # The digest is what lets a client detect a tampered or stale artifact.
    # A digest computed from anything other than the served bytes is a lie
    # that only surfaces at the consumer.
    index = client.get(AGENT_SKILLS_PATH).json()
    for skill in index["skills"]:
        served = client.get(skill["url"][len("https://www.logion.sh") :])
        assert served.status_code == 200
        digest = hashlib.sha256(served.content).hexdigest()
        assert skill["digest"] == f"sha256:{digest}", skill["name"]


def test_skill_artifact_is_served_as_markdown_with_frontmatter() -> None:
    response = client.get(SKILL_PATH)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    # The when-to-use guidance an agent needs lives in the frontmatter.
    assert response.text.startswith("---\n")
    assert "name: logion" in response.text
    assert "description:" in response.text


def test_undeclared_skill_name_cannot_read_the_content_dir() -> None:
    # The route takes a path parameter; only names declared in site.yaml may
    # resolve, or the parameter becomes an arbitrary-file read.
    for name in ("evil", "..", "legal", "landing"):
        assert (
            client.get(
                f"/.well-known/agent-skills/{name}/SKILL.md"
            ).status_code
            == 404
        ), name


def test_vendored_skill_matches_the_canonical_companion_source() -> None:
    # Vercel deploys packages/landing alone, so the artifact is vendored
    # rather than read from packages/agent-companion. This guards the copy
    # against silent drift, mirroring the brand-asset parity test.
    canonical = (
        CONTENT_DIR.parents[2] / "agent-companion" / "SKILL.md"
    ).read_bytes()
    vendored = (
        CONTENT_DIR / "agent-skills" / "logion" / "SKILL.md"
    ).read_bytes()
    assert vendored == canonical


# ── markdown alternates ───────────────────────────────────────────


@pytest.mark.parametrize(("path", "slug"), sorted(MARKDOWN_PAGES.items()))
def test_every_negotiating_page_has_a_stable_md_url(
    path: str, slug: str
) -> None:
    # Same body from the .md URL as from Accept: text/markdown on the page —
    # otherwise the two markdown paths can drift apart.
    plain = client.get(f"/{slug}.md")
    assert plain.status_code == 200
    assert plain.headers["content-type"].startswith("text/markdown")
    negotiated = client.get(path, headers={"accept": "text/markdown"})
    assert negotiated.text == plain.text


def test_markdown_alternate_points_at_the_md_url_not_the_page() -> None:
    # The audit finding this fixes: the alternate advertised the HTML URL,
    # which returns text/html to any client that cannot set Accept.
    html = client.get("/pricing").text
    assert (
        '<link rel="alternate" type="text/markdown" '
        'href="https://www.logion.sh/pricing.md"' in html
    )


def test_unknown_md_slug_is_404_not_a_page() -> None:
    assert client.get("/nope.md").status_code == 404


# ── HEAD ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/pricing",
        "/llms.txt",
        "/robots.txt",
        "/sitemap.xml",
        "/design.txt",
        AI_CATALOG_PATH,
        AGENT_SKILLS_PATH,
    ],
)
def test_head_answers_like_get_without_a_body(path: str) -> None:
    # FastAPI's APIRoute does not add HEAD alongside GET, so every one of
    # these answered 405 to the probe crawlers send before a GET.
    head = client.head(path)
    get = client.get(path)
    assert head.status_code == 200, path
    assert head.content == b""
    assert head.headers["content-length"] == get.headers["content-length"]
    assert head.headers["content-type"] == get.headers["content-type"]


# ── 404 ───────────────────────────────────────────────────────────


def test_404_gives_an_agent_somewhere_to_go() -> None:
    response = client.get("/orank-probe-test", headers={"accept": "*/*"})
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/markdown")
    body = response.text
    assert AI_CATALOG_PATH in body
    assert AGENT_SKILLS_PATH in body
    assert "/sitemap.xml" in body
    assert f"{API_BASE}/openapi.json" in body


def test_404_negotiates_html_for_browsers_and_json_for_clients() -> None:
    html = client.get("/nope", headers={"accept": "text/html"})
    assert html.status_code == 404
    assert html.headers["content-type"].startswith("text/html")
    assert "noindex" in html.text

    api = client.get("/nope", headers={"accept": "application/json"})
    assert api.status_code == 404
    assert api.json() == {"detail": "Not Found"}


# ── OpenAPI / docs ────────────────────────────────────────────────


def test_landing_does_not_publish_its_own_routes_as_the_api() -> None:
    # The marketing routes were being discovered as "the Logion API": 15
    # HTML endpoints, no versioning, no pagination. Both paths now point at
    # the real contract instead.
    for path in ("/openapi.json", "/docs"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 302, path
        assert response.headers["location"] == f"{API_BASE}{path}", path


# ── robots.txt ────────────────────────────────────────────────────


def test_robots_declares_content_signals_per_crawler_group() -> None:
    # Cloudflare's managed robots.txt currently shadows this file in
    # production; when it is turned off, ours must not lose the Content
    # Signals policy the managed one carried.
    text = client.get("/robots.txt").text
    groups = [
        block
        for block in text.split("\n\n")
        if block.startswith("User-agent:")
    ]
    assert groups
    for block in groups:
        assert "Content-Signal: search=yes,ai-input=yes,ai-train=yes" in block


def test_robots_allows_every_ai_crawler_we_name() -> None:
    text = client.get("/robots.txt").text
    for crawler in ("GPTBot", "ClaudeBot", "PerplexityBot", "CCBot"):
        assert f"User-agent: {crawler}" in text
    assert "Disallow: /\n" not in text


# ── llms.txt ──────────────────────────────────────────────────────


def test_llms_txt_indexes_the_new_discovery_surfaces() -> None:
    text = client.get("/llms.txt").text
    for path in (AI_CATALOG_PATH, AGENT_SKILLS_PATH, SKILL_PATH, "/index.md"):
        assert f"https://www.logion.sh{path}" in text, path


def test_llms_txt_links_resolve() -> None:
    # Every on-host link in the index must resolve; a broken entry in the
    # curated index is the one an agent trusts most.
    text = client.get("/llms.txt").text
    hrefs = {
        line.split("](", 1)[1].split(")", 1)[0]
        for line in text.splitlines()
        if line.startswith("- [") and "](" in line
    }
    for href in sorted(hrefs):
        if not href.startswith("https://www.logion.sh"):
            continue
        path = href[len("https://www.logion.sh") :] or "/"
        status = client.get(path, follow_redirects=False).status_code
        assert status in {200, 302}, f"{href} -> {status}"
