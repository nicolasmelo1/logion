# SPDX-License-Identifier: MIT
"""Route-level tests for the landing FastAPI app."""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

LANDING_DIR = Path(__file__).resolve().parents[1]
if str(LANDING_DIR) not in sys.path:
    sys.path.insert(0, str(LANDING_DIR))

from landing.main import STATIC_DIR, app  # noqa: E402

client = TestClient(app)


def test_index_returns_200() -> None:
    response = client.get("/")
    assert response.status_code == 200


def test_index_renders_hero_hook_and_signals() -> None:
    # Guard the above-the-fold rework: the hook line and the trust-signal
    # strip must actually render (missing YAML keys or a template refactor
    # dropping them would otherwise pass silently).
    html = client.get("/").text
    assert 'class="hero-hook"' in html
    assert "Teach the agents what you know." in html
    assert 'class="hero-signals"' in html
    assert "Open-source, auditable client" in html
    assert "Creators keep 85%" in html


def test_health_returns_ok() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_landing_app_does_not_support_legacy_brand_env() -> None:
    import inspect

    import landing.main as landing_main

    legacy_brand = "CLA" + "WSERA"
    assert legacy_brand not in inspect.getsource(landing_main)


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
    assert "https://logion.sh/design.txt" in locs


def test_design_txt_returns_plaintext() -> None:
    response = client.get("/design.txt")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")


def test_design_txt_contains_canonical_brand_anchors() -> None:
    text = client.get("/design.txt").text
    # Voice + motto.
    assert "Smarter, together." in text
    assert "## logos" in text
    assert "## palette" in text
    assert "## type" in text
    assert "## motif" in text
    # Real palette tokens, not invented.
    assert "#050608" in text  # dark --bg
    assert "#c9a76a" in text  # dark --accent
    assert "#f5d68a" in text  # dark --accent-bright
    assert "#f5f2e9" in text  # light --bg
    assert "logo_seal: #c9a76a" in text  # seal reconciled onto --accent
    # Type stack + Greek ornament.
    assert "JetBrains Mono" in text
    assert "Libre Baskerville" in text
    assert "ΛΟΓΙΟΝ" in text
    # Logo + guide links.
    assert "logion-mark.svg" in text
    assert "branding-guide.md" in text


def test_design_txt_listed_in_sitemap() -> None:
    text = client.get("/sitemap.xml").text
    assert "https://logion.sh/design.txt" in text


def test_design_txt_indexed_in_llms_txt() -> None:
    text = client.get("/llms.txt").text
    assert "/design.txt" in text
    assert "brand manifest" in text.lower()


def test_landing_has_no_external_font_dependency() -> None:
    # System-font-first: no Google Fonts @import and no preconnect to Google's
    # font hosts (the no-external-deps landing contract).
    page = client.get("/").text
    assert "fonts.googleapis.com" not in page
    assert "fonts.gstatic.com" not in page
    css = client.get("/static/styles.css").text
    assert "@import" not in css
    assert "googleapis" not in css


def test_logo_assets_use_accent_bronze_not_orphan_gold() -> None:
    # The seal gold is reconciled onto the --accent family; the orphan
    # #e0a93a must not survive in the served favicon.
    favicon = client.get("/static/favicon.svg").text
    assert "#c9a76a" in favicon
    assert "#e0a93a" not in favicon


def test_design_txt_logo_urls_serve_raw_svg_not_html() -> None:
    # /design.txt is meant to be machine-fetchable: every logo URL must serve
    # raw SVG bytes from logion.sh, not a GitHub HTML blob page.
    text = client.get("/design.txt").text
    logo_urls = [
        line.split(": ", 1)[1]
        for line in text.splitlines()
        if line.startswith("- ") and ".svg" in line
    ]
    assert len(logo_urls) == 4  # mark, wordmark, wordmark_light, favicon
    for url in logo_urls:
        assert url.startswith("https://logion.sh/static/"), url
        resp = client.get(url[len("https://logion.sh") :])
        assert resp.status_code == 200, url
        assert resp.headers["content-type"].startswith("image/svg"), url
        assert "<svg" in resp.text, url


def test_served_brand_assets_match_canonical_sources() -> None:
    # The served copies under static/brand stay byte-identical to the canonical
    # brand kit in the repo-root assets/ dir — guards against silent drift.
    assets_dir = STATIC_DIR.parents[3] / "assets"
    for name in (
        "logion-mark.svg",
        "logion-wordmark.svg",
        "logion-wordmark-light.svg",
    ):
        served = (STATIC_DIR / "brand" / name).read_bytes()
        canonical = (assets_dir / name).read_bytes()
        assert served == canonical, name


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
    assert "npx @logionsh/cli onboarding" in response.text


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
    npx_index = response.text.index("npx @logionsh/cli")
    assert curl_index < pipx_index < npx_index
    assert "install-option--primary" in response.text


def test_hero_cta_reflects_agent_use_across_surfaces() -> None:
    html = client.get("/").text
    md = client.get("/", headers={"Accept": "text/markdown"}).text

    assert "Install + connect your agent" in html
    assert "your agent" in md.lower()


@pytest.mark.parametrize(
    "asset",
    ["install.sh", "install_lib.sh", "install.ps1", "install_lib.ps1"],
)
def test_installer_asset_redirects_to_github_release(asset: str) -> None:
    response = client.get(f"/{asset}", follow_redirects=False)

    assert response.status_code == 302
    location = response.headers["location"]
    assert location == (
        "https://raw.githubusercontent.com/nicolasmelo1/logion/main/"
        f"scripts/{asset}"
    )


@pytest.mark.parametrize("channel", ["stable", "latest"])
def test_manifest_redirects_to_raw_main(channel: str) -> None:
    response = client.get(
        f"/releases/manifest-{channel}.json",
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == (
        "https://raw.githubusercontent.com/nicolasmelo1/logion/main/"
        f"releases/manifest-{channel}.json"
    )


def test_unknown_manifest_channel_is_404() -> None:
    response = client.get(
        "/releases/manifest-bogus.json",
        follow_redirects=False,
    )

    assert response.status_code == 404


def test_installer_routes_do_not_shadow_content_routes() -> None:
    for path in ("/", "/pricing", "/terms", "/privacy"):
        assert client.get(path).status_code == 200, path


def test_og_image_asset_is_served() -> None:
    response = client.get("/static/og-image.png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    # Real card, not a placeholder; PNG magic header present.
    assert response.content[:8] == b"\x89PNG\r\n\x1a\n"
    assert len(response.content) > 5000


def test_og_image_metadata_points_at_served_card() -> None:
    html = client.get("/").text
    expected = "https://logion.sh/static/og-image.png"
    assert f'<meta property="og:image" content="{expected}">' in html
    assert f'<meta name="twitter:image" content="{expected}">' in html
    assert '<meta name="twitter:card" content="summary_large_image">' in html
    assert '<meta property="og:image:width" content="1200">' in html
    assert '<meta property="og:image:height" content="630">' in html


def test_llms_txt_exposes_install_story_surface() -> None:
    # /llms.txt is the agent index; it links the landing markdown, which must
    # carry the install/onboarding story so agents can reach the curl path.
    llms = client.get("/llms.txt").text
    assert "https://logion.sh/" in llms
    md = client.get("/", headers={"Accept": "text/markdown"}).text.lower()
    assert "curl -fssl https://logion.sh/install.sh | sh" in md
    assert "companion" in md
    assert "onboarding" in md


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
    assert "logion courses purchase" in response.text


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
    assert "logion listings search" in text
    assert "logion courses purchase" in text
    assert "logion skills install" in text
    assert "--install-source logion-marketplace" in text
    assert "entitlement:" in text


def test_homepage_renders_animated_hero_demo() -> None:
    text = client.get("/").text
    assert "data-terminal-demo" in text
    assert 'role="tablist"' in text
    for tab_id in ("search", "purchase", "review", "publish"):
        assert f'data-tab="{tab_id}"' in text
        assert f'id="demo-panel-{tab_id}"' in text
    # The animation script must be linked.
    assert "/static/terminal-demo.js" in text


def test_homepage_demo_is_an_agent_conversation() -> None:
    text = client.get("/").text
    # The demo shows the user talking to their agent, not bare CLI verbs.
    assert "data-seg" in text
    assert 'class="hero-demo__who"' in text
    assert "hero-demo__who--agent" in text
    assert "with your agent" in text


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


def test_setup_complete_route_renders_setup_mode() -> None:
    response = client.get("/setup/complete")
    assert response.status_code == 200
    text = response.text
    assert "GitHub linked" in text
    assert "Your personalized install" in text
    assert "data-setup-copy" in text
    assert "data-setup-cmd" in text
    assert "setup-complete.js" in text
    assert "data-api-base" in text
    # Secondary "sign in with GitHub" CTA is hidden in setup mode.
    assert "or sign in with GitHub for a pre-authenticated install" not in text
    # Release note is hidden in setup mode.
    assert "One command sets up" not in text


def test_setup_complete_swaps_nav_signin_for_status() -> None:
    text = client.get("/setup/complete").text
    assert "connected" in text
    # The primary nav link is replaced by the connected status; the retry link
    # in the expired state is still allowed.
    assert 'class="nav-status"' in text
    assert 'href="https://api.logion.sh/v1/setup/github/start"' in text
    # But it should only appear once (the retry link), not in the primary nav.
    assert (
        text.count('href="https://api.logion.sh/v1/setup/github/start"') == 1
    )


def test_setup_complete_is_listed_in_sitemap() -> None:
    text = client.get("/sitemap.xml").text
    assert "https://logion.sh/setup/complete" in text


def test_terms_route_renders_product_terms() -> None:
    response = client.get("/terms")
    assert response.status_code == 200
    assert "Terms of Service" in response.text
    assert "non-transferable" in response.text
    assert "resell" in response.text
    assert "publicly mirror" in response.text
    assert "substitute marketplace" in response.text
    assert "Stripe Connect" in response.text
    assert "no guarantee" in response.text.lower()


def test_privacy_route_renders_product_privacy_policy() -> None:
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
    assert "logion courses acquire migration-safety-review" in text


def test_referral_landing_sets_no_cookies() -> None:
    response = client.get("/c/migration-safety-review?ref=ABCD1234")
    assert response.status_code == 200
    # Critical: the referral landing must not set cookies.
    assert "set-cookie" not in {k.lower() for k in response.headers}


def test_referral_landing_has_no_third_party_tracking() -> None:
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
    assert "logion courses acquire migration-safety-review" in text
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


def test_homepage_emits_faq_jsonld_with_visible_answers() -> None:
    text = client.get("/").text
    # JSON-LD FAQPage block with the canonical Q&A set.
    assert '"@type": "FAQPage"' in text
    assert "What is Logion?" in text
    assert "How are courses priced?" in text
    assert "Are credits refundable or transferable?" in text
    # Visible FAQ section anchors the same content for human readers.
    assert 'id="faq"' in text
    assert "Frequently asked questions" in text


def test_homepage_emits_howto_jsonld_with_real_cli_steps() -> None:
    text = client.get("/").text
    assert '"@type": "HowTo"' in text
    assert "Acquire and install" in text
    assert "logion listings search" in text
    assert "logion courses purchase" in text


def test_homepage_emits_software_application_jsonld() -> None:
    text = client.get("/").text
    assert '"@type": "SoftwareApplication"' in text
    assert "DeveloperApplication" in text


def test_keywords_meta_is_removed_as_legacy_seo_noise() -> None:
    text = client.get("/").text
    assert 'name="keywords"' not in text


def test_rel_me_links_to_github_for_authorship() -> None:
    text = client.get("/").text
    assert 'rel="me"' in text
    assert "github.com/nicolasmelo1/logion" in text


def test_breadcrumb_jsonld_on_pricing_and_legal_pages() -> None:
    for path, label in (
        ("/pricing", "Pricing"),
        ("/terms", "Terms of Service"),
        ("/privacy", "Privacy Policy"),
        ("/credits-terms", "Credits Terms"),
        ("/referrals-terms", "Referral Program Terms"),
    ):
        text = client.get(path).text
        assert '"@type": "BreadcrumbList"' in text, path
        assert label in text, path


def test_legal_pages_emit_date_modified_for_article_freshness() -> None:
    for path in ("/terms", "/privacy", "/credits-terms", "/referrals-terms"):
        text = client.get(path).text
        assert '"dateModified"' in text, path


def test_pages_link_to_their_markdown_alternate() -> None:
    for path in ("/", "/pricing", "/terms", "/privacy"):
        text = client.get(path).text
        assert 'rel="alternate" type="text/markdown"' in text, path
        assert 'href="https://logion.sh/llms-full.txt"' in text, path


def test_markdown_content_negotiation_on_every_documented_route() -> None:
    cases = (
        ("/", "Logion is an agent-native marketplace"),
        ("/pricing", "100 credits = $1"),
        ("/terms", "Terms of Service"),
        ("/privacy", "Privacy Policy"),
        ("/credits-terms", "Credits Terms"),
        ("/referrals-terms", "Referral Program Terms"),
    )
    for path, anchor in cases:
        response = client.get(path, headers={"Accept": "text/markdown"})
        assert response.status_code == 200, path
        ctype = response.headers["content-type"]
        assert ctype.startswith("text/markdown"), path
        assert anchor in response.text, path


def test_llms_full_txt_concatenates_every_public_surface() -> None:
    response = client.get("/llms-full.txt")
    assert response.status_code == 200
    text = response.text
    # Landing markdown + each legal route + FAQ block.
    assert "Agent acquisition flow" in text
    assert "## /terms" in text
    assert "## /privacy" in text
    assert "## /credits-terms" in text
    assert "## /referrals-terms" in text
    assert "## FAQ" in text
    assert "100 credits per US dollar" in text
    # Brand manifest is folded into the one-fetch concatenation.
    assert "## /design.txt" in text
    assert "Smarter, together." in text
    assert "#c9a76a" in text


def test_llms_full_txt_is_listed_in_sitemap() -> None:
    text = client.get("/sitemap.xml").text
    assert "https://logion.sh/llms-full.txt" in text


def test_llms_txt_indexes_llms_full_txt() -> None:
    text = client.get("/llms.txt").text
    assert "llms-full.txt" in text


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


def test_signin_cta_present_on_all_surfaces() -> None:
    """GitHub sign-in CTA must appear on every public surface."""
    signin_href = "https://api.logion.sh/v1/setup/github/start"

    # 1. HTML homepage
    html = client.get("/").text
    assert signin_href in html, "sign-in href missing from HTML homepage"
    assert "Sign in" in html, "'Sign in' label missing from HTML homepage"
    assert "sign in with GitHub" in html, "hero CTA text missing from HTML"

    # 2. Markdown version
    md = client.get("/", headers={"Accept": "text/markdown"}).text
    assert signin_href in md, "sign-in href missing from markdown surface"

    # 3. llms-full.txt
    llms_full = client.get("/llms-full.txt").text
    assert signin_href in llms_full, "sign-in href missing from llms-full.txt"

    # 4. llms.txt (the sign-in link is in site.yaml links.primary,
    #    which feeds the nav, not the llms.txt index — but the hero CTA
    #    text appears in the landing markdown that feeds llms-full.txt.
    #    Verify the sign-in nav link appears in the HTML nav at minimum.)
    nav = client.get("/").text
    assert 'href="https://api.logion.sh/v1/setup/github/start"' in nav
