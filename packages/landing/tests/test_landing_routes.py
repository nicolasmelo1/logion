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


def test_homepage_includes_primary_curl_install_command() -> None:
    response = client.get("/")
    assert "curl -fsSL https://logion.dev/install.sh | sh" in response.text


def test_index_returns_markdown_when_requested() -> None:
    response = client.get("/", headers={"Accept": "text/markdown"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/markdown")
    assert "# Logion" in response.text
    assert "curl -fsSL https://logion.dev/install.sh | sh" in response.text
    assert "entitlement" in response.text
    assert "publication review" in response.text


def test_homepage_links_to_legal_routes() -> None:
    response = client.get("/")
    assert 'href="/terms"' in response.text
    assert 'href="/privacy"' in response.text


def test_terms_route_renders() -> None:
    response = client.get("/terms")
    assert response.status_code == 200
    assert "Terms" in response.text


def test_privacy_route_renders() -> None:
    response = client.get("/privacy")
    assert response.status_code == 200
    assert "Privacy" in response.text
