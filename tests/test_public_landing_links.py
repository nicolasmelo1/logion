# SPDX-License-Identifier: MIT
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_landing_points_to_client_package() -> None:
    content = (
        ROOT / "packages" / "landing" / "landing" / "content" / "landing.md"
    ).read_text(encoding="utf-8")
    assert "packages/client" in content
    assert "packages/sdk-python" not in content


def test_site_yaml_points_to_client_package() -> None:
    content = (
        ROOT / "packages" / "landing" / "landing" / "content" / "site.yaml"
    ).read_text(encoding="utf-8")
    assert "packages/client" in content
    assert "packages/sdk-python" not in content
