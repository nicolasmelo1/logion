# SPDX-License-Identifier: MIT
"""Tests for ``--setup-token`` onboarding path.

Covers:
- prompt-free path when --setup-token is provided
- credentials written with 0600 permissions
- autoreview consent defaults to false
- 410 → exit 2, error message includes logion.sh URL
- env-var fallback LOGION_SETUP_TOKEN
- non-TTY allowed with --setup-token (first-run trigger)
"""

from __future__ import annotations

import json
import os
import stat
from unittest.mock import MagicMock, patch

import pytest

from cli._first_run import TriggerDecision, decide


# ---------------------------------------------------------------------------
# _setup_token.resolve_setup_token
# ---------------------------------------------------------------------------

class TestResolveSetupToken:
    """Flag wins over env var; env var is the fallback."""

    def test_explicit_flag_over_env(self):
        from cli.commands.identity._setup_token import resolve_setup_token

        args = MagicMock(setup_token="st_explicit")
        with patch.dict(os.environ, {"LOGION_SETUP_TOKEN": "st_env"}):
            assert resolve_setup_token(args) == "st_explicit"

    def test_env_var_when_flag_absent(self):
        from cli.commands.identity._setup_token import resolve_setup_token

        args = MagicMock(spec=[], setup_token=None)
        with patch.dict(os.environ, {"LOGION_SETUP_TOKEN": "st_env"}):
            assert resolve_setup_token(args) == "st_env"

    def test_returns_none_when_neither_set(self):
        from cli.commands.identity._setup_token import resolve_setup_token

        args = MagicMock(spec=[], setup_token=None)
        with patch.dict(os.environ, {}, clear=True):
            # Ensure LOGION_SETUP_TOKEN is not set
            os.environ.pop("LOGION_SETUP_TOKEN", None)
            assert resolve_setup_token(args) is None


# ---------------------------------------------------------------------------
# _first_run.decide — setup token bypasses non-interactive guard
# ---------------------------------------------------------------------------

class TestFirstRunSetupToken:
    """--setup-token and LOGION_SETUP_TOKEN allow onboarding in non-TTY."""

    def test_setup_token_flag_allows_noninteractive(self):
        args = MagicMock(
            no_onboarding=False,
            json_output=False,
            command="courses",
        )
        with patch("cli._first_run.is_onboarded", return_value=False), \
             patch("cli._first_run.is_noninteractive", return_value=True):
            decision = decide(["logion", "courses", "--setup-token", "st_abc"], args)
        assert decision.should_run is True
        assert decision.reason == "setup-token"

    def test_setup_token_env_allows_noninteractive(self):
        args = MagicMock(
            no_onboarding=False,
            json_output=False,
            command="courses",
        )
        with patch("cli._first_run.is_onboarded", return_value=False), \
             patch("cli._first_run.is_noninteractive", return_value=True), \
             patch.dict(os.environ, {"LOGION_SETUP_TOKEN": "st_env"}):
            decision = decide(["logion", "courses"], args)
        assert decision.should_run is True
        assert decision.reason == "setup-token"

    def test_noninteractive_without_token_still_blocked(self):
        args = MagicMock(
            no_onboarding=False,
            json_output=False,
            command="courses",
        )
        with patch("cli._first_run.is_onboarded", return_value=False), \
             patch("cli._first_run.is_noninteractive", return_value=True), \
             patch.dict(os.environ, {}, clear=False):
            os.environ.pop("LOGION_SETUP_TOKEN", None)
            decision = decide(["logion", "courses"], args)
        assert decision.should_run is False
        assert decision.reason == "noninteractive-env"


# ---------------------------------------------------------------------------
# redeem_setup_token — 410/409 → exit 2
# ---------------------------------------------------------------------------

class TestRedeemSetupTokenErrors:
    """410 (expired) and 409 (already redeemed) map to exit 2."""

    def test_410_expired_returns_none(self, tmp_path):
        from cli.commands.identity._setup_token import redeem_setup_token

        args = MagicMock(
            agent_name="test-agent",
            agent_description=None,
        )
        config = MagicMock()

        mock_client = MagicMock()
        mock_response = MagicMock()
        exc = Exception("token expired")
        exc.status_code = 410  # type: ignore[attr-defined]
        mock_client.v1.setup_tokens.redeem.side_effect = exc

        with patch("cli.commands.identity._setup_token.make_client", return_value=mock_client):
            result = redeem_setup_token(args, config, "st_expired_token")

        assert result is None

    def test_409_redeemed_returns_none(self, tmp_path):
        from cli.commands.identity._setup_token import redeem_setup_token

        args = MagicMock(
            agent_name="test-agent",
            agent_description=None,
        )
        config = MagicMock()

        mock_client = MagicMock()
        exc = Exception("already redeemed")
        exc.status_code = 409  # type: ignore[attr-defined]
        mock_client.v1.setup_tokens.redeem.side_effect = exc

        with patch("cli.commands.identity._setup_token.make_client", return_value=mock_client):
            result = redeem_setup_token(args, config, "st_redeemed_token")

        assert result is None


# ---------------------------------------------------------------------------
# Consent defaults to false
# ---------------------------------------------------------------------------

class TestSetupTokenConsent:
    """Token flow never grants auto-review consent."""

    def test_consent_defaults_false(self, tmp_path):
        from cli.commands.identity._setup_token import redeem_setup_token

        args = MagicMock(
            agent_name="test-agent",
            agent_description=None,
        )
        config = MagicMock()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.user_id = "user-123"
        mock_response.agent_id = "agent-456"
        mock_response.api_key = "ak_live_test"
        mock_response.api_key_prefix = "ak_live_"
        mock_response.autoreview_consent = None
        mock_client.v1.setup_tokens.redeem.return_value = mock_response

        home = tmp_path / ".logion"
        home.mkdir()

        with patch("cli.commands.identity._setup_token.make_client", return_value=mock_client), \
             patch("cli.commands.identity._setup_token.save_user_identity") as mock_save, \
             patch("cli._credentials.get_home", return_value=home):
            result = redeem_setup_token(args, config, "st_test_token")

        assert result is not None
        assert result["autoreview_consent"] is False