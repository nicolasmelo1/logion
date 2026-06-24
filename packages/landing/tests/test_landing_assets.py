# SPDX-License-Identifier: MIT
"""Static-asset tests for the landing page."""

from __future__ import annotations

import json
from pathlib import Path

from api.index import app as vercel_app

from landing.main import app

LANDING_DIR = Path(__file__).resolve().parents[1]
VERCEL_CONFIG_PATH = LANDING_DIR / "vercel.json"
VERCEL_REQUIREMENTS_PATH = LANDING_DIR / "api" / "requirements.txt"
STATIC_DIR = Path(__file__).resolve().parents[1] / "landing" / "static"


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
    # Self-host or system fonts only — no external stylesheet/font hosts.
    assert "preconnect" not in base


def test_styles_make_section_titles_serif_italic_only() -> None:
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
    assert "font-style: italic" in section_title_block
    assert "font-family: var(--mono)" in hero_title_block
    assert "font-style: italic" not in hero_title_block


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
