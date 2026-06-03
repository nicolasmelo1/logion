# SPDX-License-Identifier: MIT
"""Static-asset tests for the landing page."""

from __future__ import annotations

from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parents[1] / "landing" / "static"


def test_styles_supports_color_scheme() -> None:
    text = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
    assert "prefers-color-scheme" in text


def test_styles_supports_reduced_motion() -> None:
    text = (STATIC_DIR / "styles.css").read_text(encoding="utf-8")
    assert "prefers-reduced-motion" in text


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
