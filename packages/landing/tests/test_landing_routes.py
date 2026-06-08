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
    assert "https://logion.sh/" in locs
    assert "https://logion.sh/pricing" in locs
    assert "https://logion.sh/terms" in locs
    assert "https://logion.sh/privacy" in locs
    assert "https://logion.sh/credits-terms" in locs
    assert "https://logion.sh/referrals-terms" in locs
    assert "https://logion.sh/llms.txt" in locs


def test_llms_txt_lists_agent_readable_entrypoints() -> None:
    response = client.get("/llms.txt")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert response.text.startswith("# logion.sh")
    assert "agent-native marketplace" in response.text
    assert "[Landing (markdown)](https://logion.sh/)" in response.text
    assert "[Terms of Service](https://logion.sh/terms)" in response.text
    assert "[Privacy Policy](https://logion.sh/privacy)" in response.text
    assert "[Credits Terms](https://logion.sh/credits-terms)" in response.text
    assert (
        "[Referral Program Terms](https://logion.sh/referrals-terms)"
        in response.text
    )
    assert (
        "[GitHub repository](https://github.com/nicolasmelo1/logion)"
        in response.text
    )


def test_llms_txt_groups_public_source_and_agent_surfaces() -> None:
    text = client.get("/llms.txt").text
    assert "## Public Source" in text
    assert "## Agent Surfaces" in text
    assert "## Product Concepts" in text
    assert "CLI package" in text
    assert "Python SDK package" in text
    assert "npm wrapper package" in text
    assert "Agent companion package" in text
    assert "OpenAPI contract" in text
    assert "Release manifests" in text
    assert "/llms.txt" in text
    assert "/robots.txt" in text
    assert "/sitemap.xml" in text
    assert "Accept: text/markdown" in text


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
    assert "Agent acquisition flow" in response.text
    assert "Open-source trust layer" in response.text
    assert "lgn courses purchase" in response.text


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


def test_homepage_renders_agent_acquisition_transcript() -> None:
    text = client.get("/").text
    assert 'class="terminal-transcript"' in text
    assert "Agent acquisition flow" in text
    assert "lgn listings search" in text
    assert "lgn courses purchase" in text
    assert "lgn skills install" in text
    assert "--install-source logion-marketplace" in text
    assert "entitlement:" in text


def test_homepage_renders_animated_hero_demo() -> None:
    text = client.get("/").text
    assert "data-terminal-demo" in text
    assert 'role="tablist"' in text
    for tab_id in ("search", "purchase", "install"):
        assert f'data-tab="{tab_id}"' in text
        assert f'id="demo-panel-{tab_id}"' in text
    # The animation script must be linked.
    assert "/static/terminal-demo.js" in text


def test_homepage_renders_security_authority_section() -> None:
    text = client.get("/").text
    assert "Security is the authority" in text
    assert 'class="proof-list"' in text
    assert "course/capabilities.yaml" in text
    assert "immutable published versions" in text


def test_homepage_renders_open_source_trust_anchors() -> None:
    text = client.get("/").text
    assert "Open-source trust layer" in text
    for anchor in (
        "CLI source",
        "Python SDK",
        "npm wrapper",
        "agent companion SKILL.md",
        "public OpenAPI contract",
        "release manifests",
    ):
        assert anchor in text, anchor


def test_homepage_does_not_render_redundant_checklist_sections() -> None:
    # "Agent-readable web surface" was removed as a dedicated section —
    # those surfaces are still real (and listed in llms.txt) but the page
    # should not waste a band on a checklist that repeats the footer.
    text = client.get("/").text
    assert "Agent-readable web surface" not in text


def test_homepage_does_not_sell_credit_packs() -> None:
    text = client.get("/").text
    assert "credit pack" not in text.lower()


def test_homepage_states_credits_economy_facts() -> None:
    text = client.get("/").text
    assert "100 credits = $1" in text
    assert "85%" in text
    assert "15%" in text
    assert "no platform subscription gate" in text.lower()
    # No per-course Stripe Checkout redirect.
    assert "Stripe redirect" in text


def test_homepage_links_to_legal_routes() -> None:
    response = client.get("/")
    assert 'href="/terms"' in response.text
    assert 'href="/privacy"' in response.text
    assert 'href="/credits-terms"' in response.text
    assert 'href="/referrals-terms"' in response.text
    assert "Read terms" in response.text


def test_pricing_route_renders_credits_and_split() -> None:
    response = client.get("/pricing")
    assert response.status_code == 200
    text = response.text
    assert "Pricing" in text
    assert "100 credits = $1" in text
    assert "85" in text
    assert "15" in text
    assert "no platform subscription gate" in text.lower()
    # No subscription product offer.
    assert "/month" not in text
    assert "monthly subscription" not in text.lower()


def test_terms_route_renders_real_mvp_terms() -> None:
    response = client.get("/terms")
    assert response.status_code == 200
    assert "Terms of Service" in response.text
    assert "non-transferable" in response.text
    assert "resell" in response.text
    assert "publicly mirror" in response.text
    assert "substitute marketplace" in response.text
    assert "Stripe Connect" in response.text
    assert "no guarantee" in response.text.lower()


def test_privacy_route_renders_real_mvp_privacy_policy() -> None:
    response = client.get("/privacy")
    assert response.status_code == 200
    assert "Privacy Policy" in response.text
    assert "Stripe" in response.text
    assert "marketplace activity" in response.text
    assert "referral attribution" in response.text.lower()


def test_credits_terms_route_renders_non_cash_rules() -> None:
    response = client.get("/credits-terms")
    assert response.status_code == 200
    text = response.text
    assert "Credits Terms" in text
    assert "non-cash" in text
    assert "not transferable" in text
    assert "redeem credits for money" in text
    assert "do not expire" in text
    assert "100 credits per US dollar" in text


def test_referrals_route_renders_clawback_and_self_referral_rule() -> None:
    response = client.get("/referrals-terms")
    assert response.status_code == 200
    text = response.text
    assert "Referral Program Terms" in text
    assert "Self-referrals are prohibited" in text
    assert "clawed back" in text
    assert "Credits Terms" in text


def test_referral_landing_renders_install_command_with_code() -> None:
    response = client.get("/c/migration-safety-review?ref=ABCD1234")
    assert response.status_code == 200
    text = response.text
    assert "migration-safety-review" in text
    assert "--referral-code ABCD1234" in text
    assert "lgn courses acquire migration-safety-review" in text


def test_referral_landing_sets_no_cookies() -> None:
    response = client.get("/c/migration-safety-review?ref=ABCD1234")
    assert response.status_code == 200
    # Critical: the referral landing must not set cookies in MVP.
    assert "set-cookie" not in {k.lower() for k in response.headers}


def test_referral_landing_has_no_third_party_tracking_in_mvp() -> None:
    text = client.get("/c/migration-safety-review?ref=ABCD1234").text
    # No Google Analytics, GTM, Segment, FB pixel, or generic tracker shims.
    assert "googletagmanager" not in text.lower()
    assert "google-analytics" not in text.lower()
    assert "gtag(" not in text.lower()
    assert "segment.com" not in text.lower()
    assert "facebook.com/tr" not in text.lower()


def test_referral_landing_without_code_renders_plain_command() -> None:
    response = client.get("/c/migration-safety-review")
    assert response.status_code == 200
    text = response.text
    assert "lgn courses acquire migration-safety-review" in text
    assert "--referral-code" not in text


def test_referral_landing_rejects_invalid_slug() -> None:
    response = client.get("/c/..%2Fetc/passwd")
    assert response.status_code in (400, 404)


def test_referral_landing_rejects_invalid_referral_code() -> None:
    response = client.get(
        "/c/migration-safety-review",
        params={"ref": "drop;table users"},
    )
    assert response.status_code == 400


def test_no_page_references_per_course_stripe_checkout() -> None:
    for path in ("/", "/pricing", "/credits-terms", "/referrals-terms"):
        text = client.get(path).text
        lower = text.lower()
        assert "checkout.stripe.com" not in lower, path
        assert "stripe checkout" not in lower, path


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
    for path in (
        "/",
        "/pricing",
        "/terms",
        "/privacy",
        "/credits-terms",
        "/referrals-terms",
    ):
        body = client.get(path).text
        assert "/_vercel/insights/script.js" in body, path
        assert "window.va = window.va" in body, path
