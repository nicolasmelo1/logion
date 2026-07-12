# SPDX-License-Identifier: MIT
"""Tests for the pure issue-mention bot parser."""

from __future__ import annotations

import json
import re
from pathlib import Path

from logion_bot.commands import ISSUE_BOUNTY_AMOUNT_RE
from logion_bot.parser import IssueBotCommand, parse_issue_bot_command
from logion_bot.replies import reply_opened_unfunded

BOT = "logion-bot"
FIXTURES = Path(__file__).parent.parent / "logion_bot" / "fixtures"
COMMANDS_FIXTURE = FIXTURES / "commands.jsonl"
REPLIES_SOURCE = Path(__file__).parent.parent / "logion_bot" / "replies.py"


def _parse(body: str) -> IssueBotCommand | None:
    return parse_issue_bot_command(body, bot_login=BOT)


class TestGoldenFixtures:
    def test_golden_fixture_loads(self):
        """Parity-oriented load: every line in commands.jsonl parses."""
        lines = COMMANDS_FIXTURE.read_text().strip().splitlines()
        assert len(lines) >= 10
        for line in lines:
            obj = json.loads(line)
            cmd = _parse(obj["body"])
            exp = obj["expected"]
            if exp is None:
                assert cmd is None, obj["body"]
            else:
                assert cmd is not None, obj["body"]
                assert cmd.kind == exp["kind"]
                assert cmd.amount_credits == exp["amount_credits"]
                assert cmd.course_slug == exp["course_slug"]


def test_mention_required():
    assert _parse("bounty 250") is None


def test_case_insensitive_mention_and_verb():
    cmd = _parse("@Logion-Bot BOUNTY 250")
    assert cmd == IssueBotCommand(kind="bounty", amount_credits=250)


def test_first_verb_wins_text_before_mention_ignored():
    cmd = _parse("bounty first @logion-bot confirm later")
    assert cmd == IssueBotCommand(kind="confirm")


def test_bounty_without_amount():
    assert _parse("@logion-bot bounty") == IssueBotCommand(kind="bounty")


def test_bounty_with_amount():
    assert _parse("@logion-bot bounty 250") == IssueBotCommand(
        kind="bounty", amount_credits=250
    )


def test_bounty_with_amount_and_credits_token():
    assert _parse("@logion-bot bounty 250 credits") == IssueBotCommand(
        kind="bounty", amount_credits=250
    )


def test_bounty_with_amount_and_course():
    assert _parse("@logion-bot bounty 250 course:my-slug") == IssueBotCommand(
        kind="bounty", amount_credits=250, course_slug="my-slug"
    )


def test_malformed_amounts_yield_no_amount():
    for body in (
        "@logion-bot bounty $250",
        "@logion-bot bounty 250.50",
        "@logion-bot bounty 250 USD",
    ):
        assert _parse(body) == IssueBotCommand(kind="bounty"), body


def test_multiple_amount_tokens_yield_no_amount():
    """Money-safety pin: two amounts is ambiguous input, never last-wins."""
    for body in (
        "@logion-bot bounty 10 20",
        "@logion-bot bounty 10 credits 20",
    ):
        assert _parse(body) == IssueBotCommand(kind="bounty"), body


def test_confirm_command():
    assert _parse("@logion-bot confirm") == IssueBotCommand(kind="confirm")


def test_cancel_command():
    assert _parse("@logion-bot cancel") == IssueBotCommand(kind="cancel")


def test_help_command():
    assert _parse("@logion-bot help") == IssueBotCommand(kind="help")


def test_mention_with_no_verb_defaults_to_none():
    assert _parse("@logion-bot") is None


def test_unknown_verb_defaults_to_none():
    assert _parse("@logion-bot frobnicate") is None


def test_confirm_in_same_comment_as_bounty_is_ignored():
    """Money-safety pin: one comment can propose, never confirm."""
    assert _parse("@logion-bot bounty 250 confirm") == IssueBotCommand(
        kind="bounty", amount_credits=250
    )


def test_mention_in_code_block_ignored():
    body = "```\n@logion-bot bounty 250\n```"
    assert _parse(body) is None


def test_mention_in_inline_code_ignored():
    body = "`@logion-bot bounty 250`"
    assert _parse(body) is None


def test_mention_after_unterminated_fence_ignored():
    body = "```\n@logion-bot bounty 250"
    assert _parse(body) is None


def test_mention_before_unterminated_fence_still_parses():
    body = "@logion-bot bounty 250\n```\nsome code"
    assert _parse(body) == IssueBotCommand(kind="bounty", amount_credits=250)


def test_substring_login_does_not_match():
    assert _parse("@logion-bot-fan bounty 5") is None


def test_amount_bounds():
    assert _parse("@logion-bot bounty 0") == IssueBotCommand(kind="bounty")
    assert _parse("@logion-bot bounty 1") == IssueBotCommand(
        kind="bounty", amount_credits=1
    )
    assert _parse("@logion-bot bounty 9999999") == IssueBotCommand(
        kind="bounty", amount_credits=9_999_999
    )
    assert _parse("@logion-bot bounty 10000000") == IssueBotCommand(
        kind="bounty"
    )


def test_amount_regex_matches_integers():
    assert re.match(ISSUE_BOUNTY_AMOUNT_RE, "1")
    assert re.match(ISSUE_BOUNTY_AMOUNT_RE, "9999999")
    assert re.match(ISSUE_BOUNTY_AMOUNT_RE, "250")
    assert not re.match(ISSUE_BOUNTY_AMOUNT_RE, "0")
    assert not re.match(ISSUE_BOUNTY_AMOUNT_RE, "10000000")
    assert not re.match(ISSUE_BOUNTY_AMOUNT_RE, "250.50")
    assert not re.match(ISSUE_BOUNTY_AMOUNT_RE, "$250")


def test_last_course_token_wins():
    cmd = _parse("@logion-bot bounty 250 course:a course:b")
    assert cmd == IssueBotCommand(
        kind="bounty", amount_credits=250, course_slug="b"
    )


class TestNoUsdInReplies:
    """Grep-pin: no reply template renders USD or a dollar sign."""

    def test_no_dollar_sign_in_replies_source(self):
        src = REPLIES_SOURCE.read_text()
        assert "$" not in src

    def test_no_usd_string_in_replies_source(self):
        src = REPLIES_SOURCE.read_text()
        assert "USD" not in src


class TestRepliesGolden:
    """Golden pins for reply copy (parity: identical in both repos)."""

    def test_opened_unfunded_top_up_url_derives_from_bounty_url(self):
        reply = reply_opened_unfunded(
            bounty_url="https://staging.logion.sh/bounties/b-123",
            bounty_id="b-123",
        )
        assert "https://staging.logion.sh/bounties/b-123" in reply
        assert "Top up at https://staging.logion.sh," in reply
        assert "`logion bounties fund b-123 --yes`" in reply

    def test_no_hardcoded_host_in_replies_source(self):
        """The top-up host must derive from bounty_url, never be pinned."""
        src = REPLIES_SOURCE.read_text()
        assert "https://logion.sh" not in src
