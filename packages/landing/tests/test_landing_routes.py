# SPDX-License-Identifier: MIT
"""Route-level tests for the landing FastAPI app."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from fastapi.testclient import TestClient

from landing.main import app

client = TestClient(app)


def test_index_returns_200() -> None:
    response = client.get("/")
    assert response.status_code == 200


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_landing_app_does_not_support_legacy_brand_env() -> None:
    import inspect

    import landing.main

    legacy_brand = "CLA" + "WSERA"
    assert legacy_brand not in inspect.getsource(landing.main)


def test_robots_txt_allows_indexing_and_points_to_sitemap() -> None:
    response = client.get("/robots.txt")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "User-agent: *" in response.text
    assert "Allow: /" in response.text
    assert "User-agent: GPTBot" in response.text
    assert "User-agent: ClaudeBot" in response.text
    assert "Sitemap: https://logion.sh/sitemap.xml" in response.text


def test_sitemap_xml_lists_public_routes() -> None:
    response = client.get("/sitemap.xml")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/xml")
    root = ET.fromstring(response.text)
    namespace = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [loc.text for loc in root.findall("s:url/s:loc", namespace)]
    assert locs == [
        "https://logion.sh/",
        "https://logion.sh/terms",
        "https://logion.sh/privacy",
        "https://logion.sh/llms.txt",
    ]


def test_llms_txt_lists_agent_readable_entrypoints() -> None:
    response = client.get("/llms.txt")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text.startswith("# logion.sh")
    assert "agent-native marketplace" in response.text
    assert "[Landing (markdown)](https://logion.sh/)" in response.text
    assert "[Terms of Service](https://logion.sh/terms)" in response.text
    assert "[Privacy Policy](https://logion.sh/privacy)" in response.text
    assert (
        "[GitHub repository](https://github.com/nicolasmelo1/logion)"
        in response.text
    )


def test_homepage_includes_logion() -> None:
    response = client.get("/")
    assert "Logion" in response.text


def test_homepage_includes_install_section() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert 'id="install"' in response.text
    assert "pipx install logion-cli" in response.text
    assert "npx @logion/cli --help" in response.text


def test_homepage_includes_primary_curl_install_command() -> None:
    response = client.get("/")
    assert "curl -fsSL https://logion.sh/install.sh | sh" in response.text
    assert (
        'data-copy-command="curl -fsSL https://logion.sh/install.sh | sh"'
        in response.text
    )
    assert 'id="copy-status"' in response.text
    assert "viewBox" in response.text


def test_homepage_makes_curl_the_primary_install_path() -> None:
    response = client.get("/")
    curl_index = response.text.index("curl -fsSL")
    pipx_index = response.text.index("pipx install")
    npx_index = response.text.index("npx @logion/cli")
    assert curl_index < pipx_index
    assert curl_index < npx_index
    assert "install-option--primary" in response.text


def test_index_returns_markdown_when_requested() -> None:
    response = client.get("/", headers={"Accept": "text/markdown"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "# Logion" in response.text
    assert "curl -fsSL https://logion.sh/install.sh | sh" in response.text
    assert "Marketplace loop" in response.text
    assert "Trust model" in response.text


def test_markdown_response_is_agent_readable_without_visual_assets() -> None:
    response = client.get("/", headers={"Accept": "text/markdown"})
    assert "LOGION_HERO_FRAMES" not in response.text
    assert "hero-ascii" not in response.text
    assert "prefers-color-scheme" not in response.text


def test_homepage_includes_trust_model_language() -> None:
    response = client.get("/")
    text = response.text
    lower_text = text.lower()
    assert "course/capabilities.yaml" in text
    assert "automated scanners" in lower_text
    assert "human publication review" in lower_text
    assert "runtime sandbox enforcement is future runtime work" in lower_text


def test_homepage_includes_marketplace_terms() -> None:
    response = client.get("/")
    text = response.text
    assert "entitlement" in text
    assert "publication review" in text
    assert "bounties" in text


def test_homepage_links_to_legal_routes() -> None:
    response = client.get("/")
    assert 'href="/terms"' in response.text
    assert 'href="/privacy"' in response.text
    assert "Read terms" in response.text


def test_terms_route_renders_real_mvp_terms() -> None:
    response = client.get("/terms")
    assert response.status_code == 200
    assert "Terms of Service" in response.text
    assert "non-transferable" in response.text
    assert "resell" in response.text
    assert "publicly mirror" in response.text
    assert "substitute marketplace" in response.text


def test_privacy_route_renders_real_mvp_privacy_policy() -> None:
    response = client.get("/privacy")
    assert response.status_code == 200
    assert "Privacy Policy" in response.text
    assert "Stripe" in response.text
    assert "marketplace activity" in response.text


def test_legal_page_rejects_path_traversal() -> None:
    from unittest.mock import patch

    import pytest

    from landing.main import legal_page

    malicious_config = {
        "legal": {
            "evil": {"markdown": "../../../etc/passwd", "heading": "Evil"},
        },
    }
    with (
        patch("landing.main.content", malicious_config),
        pytest.raises(ValueError, match="escapes content directory"),
    ):
        legal_page("evil")


def test_vercel_analytics_renders_on_every_public_page() -> None:
    # The analytics tag must sit outside `{% block scripts %}` in base.html,
    # otherwise child templates that override that block (e.g. index.html
    # mounting its own app.js) silently drop the analytics script.
    for path in ("/", "/terms", "/privacy"):
        body = client.get(path).text
        assert "/_vercel/insights/script.js" in body, path
        assert "window.va = window.va" in body, path
