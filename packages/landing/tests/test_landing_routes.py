# SPDX-License-Identifier: MIT
"""Route-level tests for the landing FastAPI app."""

from __future__ import annotations

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
