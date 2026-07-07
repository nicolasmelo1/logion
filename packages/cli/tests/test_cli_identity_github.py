# SPDX-License-Identifier: MIT
"""Tests for ``logion identity github`` commands."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from cli._parser import build_parser
from cli.main import main
from logion import APIError

_CONNECT_KIND = "logion.identity.github.connect"
_STATUS_KIND = "logion.identity.github.status"
_DISCONNECT_KIND = "logion.identity.github.disconnect"


# ---------------------------------------------------------------------------
# Fake SDK
# ---------------------------------------------------------------------------


class FakeGithubIdentityResource:
    """Fake identity resource that simulates the GitHub device flow."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self._poll_responses: list[Any] = []
        self._poll_index = 0
        self.begin_response = SimpleNamespace(
            device_code="dev-code-123",
            user_code="ABCD-1234",
            verification_uri="https://github.com/login/device",
            expires_in=900,
            interval=1,
        )

    def set_poll_responses(self, responses: list[Any]) -> None:
        self._poll_responses = responses
        self._poll_index = 0

    def begin_github_device_flow(self, **kwargs: Any) -> SimpleNamespace:
        self.calls.append(("begin_github_device_flow", kwargs))
        return self.begin_response

    def poll_github_device_flow(self, **kwargs: Any) -> Any:
        self.calls.append(("poll_github_device_flow", kwargs))
        if self._poll_index < len(self._poll_responses):
            resp = self._poll_responses[self._poll_index]
            self._poll_index += 1
            return resp
        # Default response is granted
        return SimpleNamespace(
            status="connected",
            github_login="octouser",
            scope_tier="identity",
        )

    def get_github_identity(self) -> SimpleNamespace:
        self.calls.append(("get_github_identity", {}))
        return SimpleNamespace(
            connected=True,
            github_login="octouser",
            scope_tier="identity",
            status="connected",
            connected_at="2025-01-01T00:00:00Z",
        )

    def revoke_github_identity(self) -> dict[str, Any]:
        self.calls.append(("revoke_github_identity", {}))
        return {"status": "disconnected"}

    # Stubs for other identity methods so the fake is reusable.
    def create_user_with_agent(self, **_kwargs: Any) -> dict[str, Any]:
        return {}

    def add_agent_to_user(self, **_kwargs: Any) -> dict[str, Any]:
        return {}

    def rotate_api_key(self, **_kwargs: Any) -> dict[str, Any]:
        return {}

    def begin_github_authorization(self, **_kwargs: Any) -> Any:
        return SimpleNamespace()

    def complete_github_callback(self, **_kwargs: Any) -> dict[str, Any]:
        return {}


class FakeClient:
    def __init__(self, identity: FakeGithubIdentityResource) -> None:
        self.v1 = SimpleNamespace(identity=identity)

    def close(self) -> None:
        pass


@pytest.fixture(autouse=True)
def isolated_logion_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> Path:
    """Keep credentials writes out of the real ~/.logion."""
    monkeypatch.setenv("LOGION_HOME", str(tmp_path))
    return tmp_path


def _patch_client(
    monkeypatch: pytest.MonkeyPatch,
    identity: FakeGithubIdentityResource,
) -> FakeClient:
    fake = FakeClient(identity=identity)
    monkeypatch.setattr("cli._context.LogionClient", lambda **_: fake)
    return fake


# ---------------------------------------------------------------------------
# Parser registration
# ---------------------------------------------------------------------------


def test_github_subcommands_appear_in_help() -> None:
    """identity github connect/status/disconnect are registered."""
    parser = build_parser()
    # Walk the parser tree to find identity -> github subcommands.
    github_commands: list[str] = []
    for action in parser._actions:
        if not hasattr(action, "choices"):
            continue
        choices = action.choices or {}
        identity_parser = choices.get("identity")
        if identity_parser is None:
            continue
        for sub_action in identity_parser._actions:
            if not hasattr(sub_action, "choices"):
                continue
            github_parser = (sub_action.choices or {}).get("github")
            if github_parser is None:
                continue
            for g_action in github_parser._actions:
                if not hasattr(g_action, "choices"):
                    continue
                github_commands.extend((g_action.choices or {}).keys())
    assert "connect" in github_commands
    assert "status" in github_commands
    assert "disconnect" in github_commands


def test_github_connect_help() -> None:
    """identity github connect --help includes --scope-tier."""
    parser = build_parser()
    # Parse --help for the nested subcommand by looking at the parser tree.
    for action in parser._actions:
        if not hasattr(action, "choices"):
            continue
        choices = action.choices or {}
        identity_parser = choices.get("identity")
        if identity_parser is None:
            continue
        for sub_action in identity_parser._actions:
            if not hasattr(sub_action, "choices"):
                continue
            github_parser = (sub_action.choices or {}).get("github")
            if github_parser is None:
                continue
            for g_action in github_parser._actions:
                if not hasattr(g_action, "choices"):
                    continue
                connect_parser = (g_action.choices or {}).get("connect")
                if connect_parser is not None:
                    flags = {
                        opt
                        for a in connect_parser._actions
                        for opt in a.option_strings
                    }
                    assert "--scope-tier" in flags
                    assert "--json" in flags
                    return
    pytest.fail(reason="could not find identity github connect subparser")


# ---------------------------------------------------------------------------
# Device-flow connect
# ---------------------------------------------------------------------------


def _decode_json_stream(text: str) -> list[dict[str, object]]:
    """Decode multiple concatenated JSON objects from a string."""
    decoder = json.JSONDecoder()
    index = 0
    items: list[dict[str, object]] = []
    while index < len(text):
        while index < len(text) and text[index].isspace():
            index += 1
        if index >= len(text):
            break
        item, index = decoder.raw_decode(text, index)
        items.append(item)
    return items


def test_connect_device_flow_granted_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """connect emits a v1 connect envelope after pending→granted."""
    identity = FakeGithubIdentityResource()
    identity.set_poll_responses([
        SimpleNamespace(status="pending", interval=0),
        SimpleNamespace(
            status="connected",
            github_login="octouser",
            scope_tier="identity",
        ),
    ])
    _patch_client(monkeypatch, identity)

    code = main([
        "identity",
        "github",
        "connect",
        "--json",
    ])
    assert code == 0

    out = capsys.readouterr().out
    envelopes = _decode_json_stream(out)
    assert len(envelopes) == 2
    # First envelope: device_code phase
    assert envelopes[0]["kind"] == _CONNECT_KIND
    assert envelopes[0]["data"]["phase"] == "device_code"
    assert envelopes[0]["data"]["user_code"] == "ABCD-1234"
    # Second envelope: granted
    assert envelopes[1]["kind"] == _CONNECT_KIND
    assert envelopes[1]["data"]["github_login"] == "octouser"
    assert envelopes[1]["data"]["status"] == "connected"

    # Verify SDK calls
    methods = [c[0] for c in identity.calls]
    assert "begin_github_device_flow" in methods
    assert "poll_github_device_flow" in methods


def test_connect_device_flow_text_mode(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """connect in text mode prints user code and login."""
    identity = FakeGithubIdentityResource()
    identity.set_poll_responses([
        SimpleNamespace(
            status="connected",
            github_login="octouser",
            scope_tier="identity",
        ),
    ])
    _patch_client(monkeypatch, identity)

    code = main(["identity", "github", "connect"])
    assert code == 0

    out = capsys.readouterr().out
    assert "ABCD-1234" in out
    assert "octouser" in out


def _force_tty(monkeypatch: pytest.MonkeyPatch, value: bool = True) -> None:
    """Make ``sys.stdout.isatty()`` report *value* for the connect flow."""
    import sys as _sys

    monkeypatch.setattr(_sys.stdout, "isatty", lambda: value, raising=False)


def test_connect_opens_browser_on_tty(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """On an interactive TTY, connect auto-opens the browser."""
    identity = FakeGithubIdentityResource()
    _patch_client(monkeypatch, identity)
    _force_tty(monkeypatch)

    opened: list[str] = []

    def _record(url: str, new: int = 0) -> bool:  # noqa: ARG001
        opened.append(url)
        return True

    monkeypatch.setattr("webbrowser.open", _record)

    code = main(["identity", "github", "connect"])
    assert code == 0

    out = capsys.readouterr().out
    # Browser was launched with a code-prefilled URL.
    assert len(opened) == 1
    assert "ABCD-1234" in opened[0]
    assert opened[0].startswith("https://github.com/login/device")
    # Human still sees the code to confirm, not copy-paste instructions.
    assert "Opened" in out
    assert "ABCD-1234" in out
    assert "enter code" not in out


def test_connect_prefers_verification_uri_complete(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A ``verification_uri_complete`` from the API is opened verbatim."""
    identity = FakeGithubIdentityResource()
    identity.begin_response = SimpleNamespace(
        device_code="dev-code-123",
        user_code="ABCD-1234",
        verification_uri="https://github.com/login/device",
        verification_uri_complete=(
            "https://github.com/login/device?user_code=ABCD-1234"
        ),
        expires_in=900,
        interval=1,
    )
    _patch_client(monkeypatch, identity)
    _force_tty(monkeypatch)

    opened: list[str] = []

    def _record(url: str, new: int = 0) -> bool:  # noqa: ARG001
        opened.append(url)
        return True

    monkeypatch.setattr("webbrowser.open", _record)

    code = main(["identity", "github", "connect"])
    assert code == 0
    capsys.readouterr()

    assert opened == ["https://github.com/login/device?user_code=ABCD-1234"]


def test_connect_no_browser_flag_skips_launch(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """--no-browser prints copy-paste instructions and never launches."""
    identity = FakeGithubIdentityResource()
    _patch_client(monkeypatch, identity)
    _force_tty(monkeypatch)

    def _boom(url: str, new: int = 0) -> bool:  # noqa: ARG001
        raise AssertionError("browser must not open with --no-browser")

    monkeypatch.setattr("webbrowser.open", _boom)

    code = main(["identity", "github", "connect", "--no-browser"])
    assert code == 0

    out = capsys.readouterr().out
    assert "and enter code: ABCD-1234" in out


def test_connect_no_tty_prints_manual_instructions(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Without a TTY (agent/CI), connect falls back to copy-paste."""
    identity = FakeGithubIdentityResource()
    _patch_client(monkeypatch, identity)
    _force_tty(monkeypatch, value=False)

    def _boom(url: str, new: int = 0) -> bool:  # noqa: ARG001
        raise AssertionError("browser must not open without a TTY")

    monkeypatch.setattr("webbrowser.open", _boom)

    code = main(["identity", "github", "connect"])
    assert code == 0

    out = capsys.readouterr().out
    assert "enter code: ABCD-1234" in out


def test_connect_forwards_scope_tier(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """connect --scope-tier repo forwards to SDK."""
    identity = FakeGithubIdentityResource()
    _patch_client(monkeypatch, identity)

    code = main([
        "identity",
        "github",
        "connect",
        "--scope-tier",
        "repo",
        "--json",
    ])
    assert code == 0
    capsys.readouterr()  # discard

    begin_calls = [
        c for c in identity.calls if c[0] == "begin_github_device_flow"
    ]
    assert len(begin_calls) == 1
    assert begin_calls[0][1]["scope_tier"] == "repo"


def test_connect_caps_wait_and_poll_sleep(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """connect clamps long device-flow waits to the documented cap."""
    identity = FakeGithubIdentityResource()
    identity.begin_response = SimpleNamespace(
        device_code="dev-code-123",
        user_code="ABCD-1234",
        verification_uri="https://github.com/login/device",
        expires_in=10_000,
        interval=10_000,
    )
    identity.set_poll_responses([
        SimpleNamespace(status="pending", interval=10_000),
        SimpleNamespace(
            status="connected",
            github_login="octouser",
            scope_tier="identity",
        ),
    ])
    _patch_client(monkeypatch, identity)

    sleeps: list[float] = []
    monkeypatch.setattr(
        "cli.commands.identity.github.time.sleep",
        sleeps.append,
    )

    code = main(["identity", "github", "connect"])
    assert code == 0
    capsys.readouterr()

    assert sleeps
    assert max(sleeps) <= 30
    assert all(sleep > 0 for sleep in sleeps)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


def test_status_json_envelope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """status emits a v1 status envelope with connected state."""
    identity = FakeGithubIdentityResource()
    _patch_client(monkeypatch, identity)

    code = main(["identity", "github", "status", "--json"])
    assert code == 0

    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["kind"] == _STATUS_KIND
    assert data["data"]["connected"] is True
    assert data["data"]["github_login"] == "octouser"


def test_status_text_mode_connected(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """status in text mode prints Connected as @login."""
    identity = FakeGithubIdentityResource()
    _patch_client(monkeypatch, identity)

    code = main(["identity", "github", "status"])
    assert code == 0

    out = capsys.readouterr().out
    assert "octouser" in out
    assert "Connected" in out


def test_status_text_mode_not_connected(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """status prints Not connected when not linked."""

    class NotConnectedResource(FakeGithubIdentityResource):
        def get_github_identity(self) -> SimpleNamespace:
            self.calls.append(("get_github_identity", {}))
            return SimpleNamespace(
                connected=False,
                github_login=None,
                scope_tier=None,
                status=None,
                connected_at=None,
            )

    identity = NotConnectedResource()
    _patch_client(monkeypatch, identity)

    code = main(["identity", "github", "status"])
    assert code == 0

    out = capsys.readouterr().out
    assert "Not connected" in out


def test_status_json_api_error_envelope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """status emits structured JSON for API errors."""

    class RaisingResource(FakeGithubIdentityResource):
        def get_github_identity(self) -> SimpleNamespace:
            self.calls.append(("get_github_identity", {}))
            raise APIError(401, "missing api key")

    identity = RaisingResource()
    _patch_client(monkeypatch, identity)

    code = main(["identity", "github", "status", "--json"])
    assert code == 1

    err = capsys.readouterr().err
    payload = json.loads(err)
    assert payload["kind"] == "logion.error"
    assert payload["data"]["code"] == "auth_missing"
    assert payload["data"]["exit_code"] == 1


# ---------------------------------------------------------------------------
# Disconnect
# ---------------------------------------------------------------------------


def test_disconnect_requires_yes_text_mode(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """disconnect without --yes in text mode exits 2."""
    identity = FakeGithubIdentityResource()
    _patch_client(monkeypatch, identity)

    code = main(["identity", "github", "disconnect"])
    assert code == 2

    err = capsys.readouterr().err
    assert "--yes" in err
    # SDK was never called
    methods = [c[0] for c in identity.calls]
    assert "revoke_github_identity" not in methods


def test_disconnect_requires_yes_json_mode(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """disconnect without --yes in JSON mode emits structured error."""
    identity = FakeGithubIdentityResource()
    _patch_client(monkeypatch, identity)

    code = main(["identity", "github", "disconnect", "--json"])
    assert code == 2

    err = capsys.readouterr().err
    payload = json.loads(err)
    assert payload["kind"] == "logion.error"
    assert payload["data"]["code"] == "confirmation_required"


def test_disconnect_with_yes_json(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """disconnect --yes emits a v1 disconnect envelope."""
    identity = FakeGithubIdentityResource()
    _patch_client(monkeypatch, identity)

    code = main(["identity", "github", "disconnect", "--yes", "--json"])
    assert code == 0

    out = capsys.readouterr().out
    data = json.loads(out)
    assert data["kind"] == _DISCONNECT_KIND
    assert data["data"]["status"] == "disconnected"


def test_disconnect_with_yes_text_mode(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """disconnect --yes in text mode prints confirmation."""
    identity = FakeGithubIdentityResource()
    _patch_client(monkeypatch, identity)

    code = main(["identity", "github", "disconnect", "--yes"])
    assert code == 0

    out = capsys.readouterr().out
    assert "disconnected" in out.lower()


def test_disconnect_json_api_error_envelope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """disconnect emits structured JSON for GitHub identity conflicts."""

    class RaisingResource(FakeGithubIdentityResource):
        def revoke_github_identity(self) -> dict[str, Any]:
            self.calls.append(("revoke_github_identity", {}))
            raise APIError(409, "github_identity_conflict")

    identity = RaisingResource()
    _patch_client(monkeypatch, identity)

    code = main(["identity", "github", "disconnect", "--yes", "--json"])
    assert code == 1

    err = capsys.readouterr().err
    payload = json.loads(err)
    assert payload["kind"] == "logion.error"
    assert payload["data"]["code"] == "github_identity_conflict"
    assert payload["data"]["exit_code"] == 1


# ---------------------------------------------------------------------------
# No token leakage
# ---------------------------------------------------------------------------


def test_no_token_in_connect_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """connect output only contains expected fields, no token fields."""
    identity = FakeGithubIdentityResource()
    _patch_client(monkeypatch, identity)

    code = main(["identity", "github", "connect", "--json"])
    assert code == 0

    out = capsys.readouterr().out
    # The granted envelope should not contain access_token or token fields
    # (the API response model doesn't include them; if they appear, the
    # handler is leaking sensitive data).
    envelopes = _decode_json_stream(out)
    granted = envelopes[-1]
    assert "access_token" not in granted["data"]
    assert "token" not in granted["data"]


def test_connect_json_api_error_envelope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """connect emits structured JSON for backend GitHub OAuth outages."""

    class RaisingResource(FakeGithubIdentityResource):
        def begin_github_device_flow(self, **kwargs: Any) -> SimpleNamespace:
            self.calls.append(("begin_github_device_flow", kwargs))
            raise APIError(503, "github_oauth_unconfigured")

    identity = RaisingResource()
    _patch_client(monkeypatch, identity)

    code = main(["identity", "github", "connect", "--json"])
    assert code == 1

    err = capsys.readouterr().err
    payload = json.loads(err)
    assert payload["kind"] == "logion.error"
    assert payload["data"]["code"] == "github_oauth_unconfigured"
    assert payload["data"]["exit_code"] == 1


def test_no_token_in_status_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """status output only contains expected fields, no token fields."""
    identity = FakeGithubIdentityResource()
    _patch_client(monkeypatch, identity)

    code = main(["identity", "github", "status", "--json"])
    assert code == 0

    out = capsys.readouterr().out
    data = json.loads(out)
    assert "access_token" not in data["data"]
    assert "token" not in data["data"]
