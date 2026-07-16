# SPDX-License-Identifier: MIT
"""Tests for ``--setup-token`` onboarding path.

Covers:
- setup token resolution precedence (flag over env var)
- non-interactive first-run allowance via ``LOGION_SETUP_TOKEN``
- 409/410 redeem failures returning ``None``
- token flow defaulting auto-review consent to ``False``
- refusal to overwrite existing stored credentials
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

from cli._first_run import decide

# ---------------------------------------------------------------------------
# _setup_token.resolve_setup_token
# ---------------------------------------------------------------------------


class TestResolveSetupToken:
    """Flag wins over env var; env var is the fallback."""

    def test_explicit_flag_over_env(self):
        from cli.commands.identity._setup_token import (
            resolve_setup_token,
        )

        args = MagicMock(setup_token="st_explicit")
        with patch.dict(os.environ, {"LOGION_SETUP_TOKEN": "st_env"}):
            assert resolve_setup_token(args) == "st_explicit"

    def test_env_var_when_flag_absent(self):
        from cli.commands.identity._setup_token import (
            resolve_setup_token,
        )

        args = MagicMock(spec=[], setup_token=None)
        with patch.dict(os.environ, {"LOGION_SETUP_TOKEN": "st_env"}):
            assert resolve_setup_token(args) == "st_env"

    def test_returns_none_when_neither_set(self):
        from cli.commands.identity._setup_token import (
            resolve_setup_token,
        )

        args = MagicMock(spec=[], setup_token=None)
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("LOGION_SETUP_TOKEN", None)
            assert resolve_setup_token(args) is None


# ---------------------------------------------------------------------------
# _first_run.decide — setup token bypasses non-interactive guard
# ---------------------------------------------------------------------------


class TestFirstRunSetupToken:
    """--setup-token and LOGION_SETUP_TOKEN allow
    onboarding in non-TTY."""

    def test_setup_token_env_allows_noninteractive(self):
        args = MagicMock(
            no_onboarding=False,
            json_output=False,
            command="courses",
        )
        with (
            patch("cli._first_run.is_onboarded", return_value=False),
            patch(
                "cli._first_run.is_noninteractive",
                return_value=True,
            ),
            patch.dict(os.environ, {"LOGION_SETUP_TOKEN": "st_env"}),
        ):
            decision = decide(["logion", "courses"], args)
        assert decision.should_run is True
        assert decision.reason == "setup-token"

    def test_noninteractive_without_token_still_blocked(self):
        args = MagicMock(
            no_onboarding=False,
            json_output=False,
            command="courses",
        )
        with (
            patch("cli._first_run.is_onboarded", return_value=False),
            patch(
                "cli._first_run.is_noninteractive",
                return_value=True,
            ),
            patch.dict(os.environ, {}, clear=False),
        ):
            os.environ.pop("LOGION_SETUP_TOKEN", None)
            decision = decide(["logion", "courses"], args)
        assert decision.should_run is False
        assert decision.reason == "noninteractive-env"


# ---------------------------------------------------------------------------
# redeem_setup_token — 410/409 → exit 2
# ---------------------------------------------------------------------------


class TestRedeemSetupTokenErrors:
    """410 (expired) and 409 (already redeemed)
    map to exit 2."""

    def test_410_expired_returns_none_and_prints_mint_url(self):
        from cli.commands.identity._setup_token import (
            redeem_setup_token,
        )

        args = MagicMock(
            agent_name="test-agent",
            agent_description=None,
        )
        config = MagicMock()

        mock_client = MagicMock()
        exc = Exception("token expired")
        exc.status_code = 410  # type: ignore[attr-defined]
        mock_client.v1.github_setup.redeem_token.side_effect = exc

        with (
            patch(
                "cli.commands.identity._setup_token.make_client",
                return_value=mock_client,
            ),
            patch("cli.commands.identity._setup_token.print_err") as print_err,
        ):
            result = redeem_setup_token(args, config, "st_expired_token")

        assert result is None
        print_err.assert_called_once()
        assert (
            "https://api.logion.sh/v1/setup/github/start"
            in (print_err.call_args.args[0])
        )

    def test_409_redeemed_returns_none(self):
        from cli.commands.identity._setup_token import (
            redeem_setup_token,
        )

        args = MagicMock(
            agent_name="test-agent",
            agent_description=None,
        )
        config = MagicMock()

        mock_client = MagicMock()
        exc = Exception("already redeemed")
        exc.status_code = 409  # type: ignore[attr-defined]
        mock_client.v1.github_setup.redeem_token.side_effect = exc

        with patch(
            "cli.commands.identity._setup_token.make_client",
            return_value=mock_client,
        ):
            result = redeem_setup_token(args, config, "st_redeemed_token")

        assert result is None


# ---------------------------------------------------------------------------
# Consent defaults to false
# ---------------------------------------------------------------------------


class TestSetupTokenConsent:
    """Token flow never grants auto-review consent."""

    def test_consent_defaults_false(self):
        from cli.commands.identity._setup_token import (
            redeem_setup_token,
        )

        args = MagicMock(
            agent_name="test-agent",
            agent_description=None,
        )
        config = MagicMock()

        mock_client = MagicMock()
        mock_response = MagicMock(
            user_id="user-123",
            agent_id="agent-456",
            api_key="ak_live_test",  # pragma: allowlist secret
            api_key_prefix="ak_live_",  # pragma: allowlist secret
        )
        mock_client.v1.github_setup.redeem_token.return_value = mock_response

        with (
            patch(
                "cli.commands.identity._setup_token.make_client",
                return_value=mock_client,
            ),
            patch("cli.commands.identity._setup_token.save_user_identity"),
            patch("cli._credentials.get_home"),
        ):
            result = redeem_setup_token(args, config, "st_test_token")

        assert result is not None
        assert result["autoreview_consent"] is False


class TestHandleOnboardingSetupToken:
    """Onboarding should refuse setup-token runs
    that would clobber credentials."""

    def test_existing_credentials_block_setup_token_path(self):
        from cli.commands.identity.onboarding import handle_onboarding

        args = MagicMock()
        with (
            patch(
                "cli.commands.identity.onboarding.resolve_config_from_args",
                return_value=MagicMock(json_output=False),
            ),
            patch(
                "cli.commands.identity.onboarding.resolve_setup_token",
                return_value="st_existing",
            ),
            patch(
                "cli.commands.identity.onboarding.stored_user_id",
                return_value="user-existing",
            ),
            patch(
                "cli.commands.identity.onboarding.redeem_setup_token"
            ) as redeem,
            patch("cli.commands.identity.onboarding.print_err") as print_err,
        ):
            rc = handle_onboarding(args)

        assert rc == 2
        redeem.assert_not_called()
        print_err.assert_called_once()
        assert (
            "Refusing to overwrite stored credentials"
            in (print_err.call_args.args[0])
        )
