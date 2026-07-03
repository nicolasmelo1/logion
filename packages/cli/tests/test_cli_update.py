# SPDX-License-Identifier: MIT
"""Tests for ``logion update``."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any
from urllib.request import Request

from cli.commands.update import _download_installer, _installer_command


def test_update_installer_command_defaults_to_latest_no_onboarding() -> None:
    """update uses the full installer, including the companion step."""
    args = argparse.Namespace(
        channel="latest",
        version=None,
        installer=None,
        dry_run=False,
    )

    command = _installer_command(Path("/tmp/install.sh"), args)

    assert command == [
        "sh",
        "/tmp/install.sh",
        "--channel",
        "latest",
        "--no-onboarding",
        "--update",
    ]
    assert "--cli-only" not in command
    assert "--skill-only" not in command


def test_update_downloads_installer_with_cli_headers(
    monkeypatch: Any,
) -> None:
    """CDNs must not see the default Python urllib user agent."""
    seen: dict[str, Any] = {}

    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return b"#!/bin/sh\n"

    def fake_urlopen(request: Request, *, timeout: float) -> Response:
        seen["request"] = request
        seen["timeout"] = timeout
        return Response()

    monkeypatch.setattr(
        "cli.commands.update.urllib.request.urlopen", fake_urlopen
    )

    path = _download_installer("https://logion.sh/install.sh", timeout=None)

    assert path.read_bytes() == b"#!/bin/sh\n"
    assert seen["timeout"] == 30.0
    request = seen["request"]
    assert isinstance(request, Request)
    assert request.full_url == "https://logion.sh/install.sh"
    assert request.headers["User-agent"].startswith("logion-cli/")
    assert "text/plain" in request.headers["Accept"]


def test_update_installer_command_forwards_options() -> None:
    """update forwards version, installer backend, and dry-run."""
    args = argparse.Namespace(
        channel="stable",
        version="0.1.3",
        installer="pipx",
        dry_run=True,
    )

    command = _installer_command(Path("/tmp/install.sh"), args)

    assert command == [
        "sh",
        "/tmp/install.sh",
        "--channel",
        "stable",
        "--no-onboarding",
        "--update",
        "--version",
        "0.1.3",
        "--installer",
        "pipx",
        "--dry-run",
    ]
