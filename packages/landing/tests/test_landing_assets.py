# SPDX-License-Identifier: MIT
"""Static-asset tests for the landing page."""

from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

LANDING_DIR = Path(__file__).resolve().parents[1]
if str(LANDING_DIR) not in sys.path:
    sys.path.insert(0, str(LANDING_DIR))
VERCEL_CONFIG_PATH = LANDING_DIR / "vercel.json"
VERCEL_REQUIREMENTS_PATH = LANDING_DIR / "api" / "requirements.txt"
STATIC_DIR = Path(__file__).resolve().parents[1] / "landing" / "static"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"unable to load {name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


_main_module = _load_module(
    "landing.main",
    LANDING_DIR / "landing" / "main.py",
)
_api_module = _load_module("api.index", LANDING_DIR / "api" / "index.py")
app = _main_module.app
vercel_app = _api_module.app


def test_styles_supports_color_scheme() -> None:
    text = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
    assert "prefers-color-scheme" in text


def test_styles_supports_reduced_motion() -> None:
    text = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in text


def test_styles_has_no_external_font_imports() -> None:
    text = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in text
    assert "fonts.gstatic.com" not in text
    assert "@import" not in text


def test_base_template_has_no_external_preconnect() -> None:
    base = (
        Path(__file__).resolve().parents[1]
        / "landing"
        / "templates"
        / "base.html"
    ).read_text(encoding="utf-8")
    assert "fonts.googleapis.com" not in base
    assert "fonts.gstatic.com" not in base
    # No preconnect to an external host (the no-external-font-deps contract).
    # Same-origin / non-font resource hints are allowed, so assert on the
    # actual link targets rather than banning the bare word "preconnect".
    # Handle either quote style and multi-token rel values
    # (e.g. rel="preconnect dns-prefetch").
    for link in re.findall(r"<link\b[^>]*>", base, flags=re.IGNORECASE):
        rel_match = re.search(r"""rel\s*=\s*["']([^"']*)["']""", link)
        if not rel_match:
            continue
        if "preconnect" not in rel_match.group(1).lower().split():
            continue
        href_match = re.search(r"""href\s*=\s*["']([^"']*)["']""", link)
        href = href_match.group(1) if href_match else ""
        assert not re.match(r"(https?:)?//", href), (
            f"external preconnect not allowed: {href}"
        )


def test_styles_use_a_deliberate_two_family_heading_scale() -> None:
    text = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
    section_title_block = text.split(".content-section h2 {", maxsplit=1)[
        1
    ].split("}", maxsplit=1)[0]
    hero_title_block = text.split(".hero-copy h1 {", maxsplit=1)[1].split(
        "}",
        maxsplit=1,
    )[0]
    assert "--serif:" in text
    assert "Times New Roman" in text
    assert "font-family: var(--serif)" in section_title_block
    assert "font-style: normal" in section_title_block
    assert "font-family: var(--mono)" in hero_title_block
    assert "font-style: italic" not in hero_title_block


def test_styles_make_product_examples_responsive() -> None:
    text = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
    assert ".product-example {" in text
    assert ".product-example__header {" in text
    assert ".product-example dl {" in text
    assert "grid-template-columns: 1fr" in text


def test_primary_copy_command_does_not_truncate() -> None:
    text = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
    cta_cmd_block = text.split(".cta-cmd {", maxsplit=1)[1].split(
        "}",
        maxsplit=1,
    )[0]
    copy_cta_block = text.split(".copy-cta {", maxsplit=1)[1].split(
        "}",
        maxsplit=1,
    )[0]
    primary_cta_block = text.split(".cta--primary {", maxsplit=1)[1].split(
        "}",
        maxsplit=1,
    )[0]
    assert "width: min(100%, 900px)" in copy_cta_block
    assert "min-height: 58px" in primary_cta_block
    assert "overflow-wrap: anywhere" in cta_cmd_block
    assert "text-overflow: ellipsis" not in cta_cmd_block


def test_setup_command_truncates_with_scroll_and_gold_warning() -> None:
    # The personalized install command (with setup token) is much longer
    # than the standard curl line: one line, ellipsis, horizontal scroll.
    # The base .cta-cmd (homepage curl) must stay untruncated — guarded by
    # test_primary_copy_command_does_not_truncate above.
    text = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
    setup_cmd_block = text.split(".cta--setup .cta-cmd {", maxsplit=1)[
        1
    ].split(
        "}",
        maxsplit=1,
    )[0]
    assert "text-overflow: ellipsis" in setup_cmd_block
    assert "overflow-x: auto" in setup_cmd_block
    # Token-safety warning renders in the design's bright accent gold.
    warning_block = text.split(".setup-warning {", maxsplit=1)[1].split(
        "}",
        maxsplit=1,
    )[0]
    assert "color: var(--accent-bright)" in warning_block


def test_setup_complete_js_redirects_home_on_bad_handoff() -> None:
    # Invalid/expired/used handoffs (and direct visits) bounce back to the
    # home page — there is no in-page expired/retry state.
    text = (STATIC_DIR / "setup-complete.js").read_text(encoding="utf-8")
    assert 'window.location.replace("/")' in text
    assert "showExpired" not in text
    assert "data-setup-retry" not in text


def test_hero_frames_exports_multiple_frames() -> None:
    text = (STATIC_DIR / "ascii" / "hero_frames.js").read_text(
        encoding="utf-8"
    )
    assert "LOGION_HERO_FRAMES" in text
    # Frames are produced via buildFrame(...); require 6-16.
    frame_calls = text.count("buildFrame(")
    # one call appears in the function definition; subtract it
    frame_count = max(0, frame_calls - 1)
    assert 6 <= frame_count <= 16, f"expected 6-16 frames, found {frame_count}"


def test_app_js_has_frame_swap_logic() -> None:
    text = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    assert "LOGION_HERO_FRAMES" in text
    assert "setInterval" in text
    assert "prefers-reduced-motion" in text


def test_app_js_has_clipboard_copy_logic() -> None:
    text = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    assert "data-copy-command" in text
    assert "navigator.clipboard.writeText" in text
    assert "Copied to clipboard" in text


def test_app_js_pauses_animation_without_horizon_line_on_tab_return() -> None:
    text = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    assert "Horizon line" not in text
    assert "startLoop" in text
    assert "stopLoop" in text
    assert "cancelAnimationFrame" in text
    assert "visibilitychange" in text
    assert "pagehide" in text


def test_styles_smooth_scroll_respects_reduced_motion() -> None:
    text = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
    assert "scroll-behavior: smooth" in text
    # Reduced motion must fall back to instant jumps.
    assert "scroll-behavior: auto" in text


def test_section_stacking_is_wired() -> None:
    # Sections pin and stack over each other; app.js sets per-section
    # sticky tops (negative for sections taller than the viewport so
    # nothing becomes unreadable), fades the pinned section as the next
    # covers it (no opaque background — the zeus backdrop stays visible),
    # and recomputes when heights change.
    css = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
    assert "position: sticky" in css
    js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    assert "initSectionStack" in js
    assert "updateSectionFade" in js
    assert 'addEventListener("toggle", initSectionStack)' in js
    # Wheel smoothing: rAF-lerped, never hijacking touch/zoom/reduced.
    assert "initSmoothWheel" in js
    assert "if (reduced.matches || coarse.matches) return;" in js
    assert "if (e.ctrlKey || e.defaultPrevented) return;" in js


def test_hero_terminal_has_a_desktop_sticky_scroll_runway() -> None:
    css = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
    assert ".hero-demo-col {" in css
    assert "padding-bottom: 28vh" in css
    assert "position: sticky" in css
    assert "top: 24px" in css


def test_section_demo_tabs_are_accessible() -> None:
    js = (STATIC_DIR / "section-demo.js").read_text(encoding="utf-8")
    assert "data-section-demo" in js
    assert 'setAttribute("aria-selected"' in js
    assert 'setAttribute("aria-hidden"' in js
    assert 'event.key === "ArrowRight"' in js
    assert 'event.key === "ArrowLeft"' in js
    assert "tabIndex" in js


def test_all_terminal_animations_are_viewport_triggered() -> None:
    hero_js = (STATIC_DIR / "terminal-demo.js").read_text(encoding="utf-8")
    section_js = (STATIC_DIR / "section-demo.js").read_text(encoding="utf-8")
    for js in (hero_js, section_js):
        assert "IntersectionObserver" in js
        assert "entry.isIntersecting" in js
        assert "prefers-reduced-motion: reduce" in js
    assert "frames.forEach(clearFrame)" in section_js
    assert "typeInto" in section_js


def test_terminal_roles_use_distinct_accent_and_muted_colors() -> None:
    css = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")

    def blocks(selector: str) -> str:
        return "\n".join(
            re.findall(rf"{re.escape(selector)}\s*{{([^}}]+)}}", css)
        )

    user_block = blocks(".hero-demo__who")
    agent_block = blocks(".hero-demo__who--agent")
    prompt_block = blocks(".hero-demo__who--run")
    output_block = blocks(".hero-demo__turn--out .hero-demo__seg")
    assert "color: var(--accent-bright)" in user_block
    assert "color: var(--fg-dim)" in agent_block
    assert "color: var(--accent-bright)" in prompt_block
    assert "color: var(--muted)" in output_block


def test_app_js_has_mobile_and_reduced_motion_low_cost_paths() -> None:
    # Perf contract for mobile Firefox (issue #174): coarse pointers get a
    # capped frame budget and lower scene density; reduced motion renders a
    # single static frame instead of running the rAF loop; the full-screen
    # ASCII silhouette must never take per-frame style writes when the
    # eased parallax value is unchanged (each write invalidates a huge
    # text layer on Gecko).
    text = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    assert "pointer: coarse" in text
    assert "COARSE_FRAME_INTERVAL" in text
    assert "renderStaticFrame" in text
    # Hero particles stop drawing when scrolled out of view.
    assert "IntersectionObserver" in text
    # The light-mode media query must not be constructed per frame.
    assert text.count('matchMedia("(prefers-color-scheme: light)")') == 1
    # The zeus backdrop is a pre-rendered raster (zeus.webp); the text
    # asset is never fetched or laid out. Its parallax bails out on
    # coarse/reduced and only writes when the eased transform changed.
    assert "zeus.txt" not in text
    assert "silLastTransform" in text
    assert "if (reduced.matches || coarse.matches) return;" in text


def test_vercel_entrypoint_exports_landing_app() -> None:
    assert vercel_app is app


def test_vercel_config_rewrites_to_api_function() -> None:
    config = json.loads(VERCEL_CONFIG_PATH.read_text(encoding="utf-8"))
    assert "functions" not in config
    assert config["rewrites"] == [
        {
            "source": "/(.*)",
            "destination": "/api/index",
        }
    ]


def test_vercel_api_requirements_include_runtime_deps() -> None:
    text = VERCEL_REQUIREMENTS_PATH.read_text(encoding="utf-8")
    for requirement in (
        "fastapi==",
        "jinja2==",
        "markdown-it-py==",
        "pyyaml==",
    ):
        assert requirement in text
