# SPDX-License-Identifier: MIT
"""Tests for the GitHub-Releases-derived hero version readout."""

from __future__ import annotations

import io
import json
from typing import NoReturn

import pytest
from fastapi.testclient import TestClient

from landing import main


def _reset_cache() -> None:
    main._readout_cache["value"] = None
    main._readout_cache["at"] = 0.0


def test_fallback_is_channel_only() -> None:
    # The static fallback must never carry a hard-coded version that drifts.
    fallback = main._fallback_readout()
    assert fallback == "stable channel"
    assert not fallback.startswith("v")


def test_release_readout_uses_fetched_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reset_cache()
    monkeypatch.setattr(
        main, "_fetch_release_readout", lambda: "v9.9.9 · stable"
    )
    assert main.release_readout(now=0.0) == "v9.9.9 · stable"


def test_release_readout_falls_back_when_fetch_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reset_cache()
    monkeypatch.setattr(main, "_fetch_release_readout", lambda: None)
    assert main.release_readout(now=0.0) == main._fallback_readout()


def test_release_readout_caches_within_ttl(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reset_cache()
    calls = {"n": 0}

    def fake_fetch() -> str:
        calls["n"] += 1
        return f"v0.0.{calls['n']} · stable"

    monkeypatch.setattr(main, "_fetch_release_readout", fake_fetch)
    first = main.release_readout(now=100.0)
    second = main.release_readout(now=100.0 + main._READOUT_TTL_SECONDS - 1)
    third = main.release_readout(now=100.0 + main._READOUT_TTL_SECONDS + 1)

    assert first == "v0.0.1 · stable"
    assert second == first  # within TTL → cached, no refetch
    assert third == "v0.0.2 · stable"  # past TTL → refetched
    assert calls["n"] == 2


def test_fetch_parses_cli_version_from_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = {
        "channel": "stable",
        "packages": {"logion-cli": {"version": "1.2.3"}},
    }

    class _Resp(io.BytesIO):
        def __enter__(self) -> _Resp:
            return self

        def __exit__(self, *exc: object) -> None:
            self.close()

    def fake_urlopen(*args: object, **kwargs: object) -> _Resp:
        del args, kwargs
        return _Resp(json.dumps(manifest).encode("utf-8"))

    monkeypatch.setattr(main.urllib.request, "urlopen", fake_urlopen)
    assert main._fetch_release_readout() == "v1.2.3 · stable"


def test_fetch_returns_none_on_network_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def boom(*args: object, **kwargs: object) -> NoReturn:
        del args, kwargs
        raise OSError("no network")

    monkeypatch.setattr(main.urllib.request, "urlopen", boom)
    assert main._fetch_release_readout() is None


def test_index_renders_live_readout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _reset_cache()
    monkeypatch.setattr(
        main, "_fetch_release_readout", lambda: "v7.7.7 · stable"
    )
    client = TestClient(main.app)
    html = client.get("/").text
    assert "v7.7.7 · stable" in html
