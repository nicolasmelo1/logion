# SPDX-License-Identifier: MIT
"""Shared helpers for referrals commands."""

from __future__ import annotations

import sys

from cli._output import to_data


def emit_code_human(result: object) -> None:
    """Render a referral code result as human-readable key: value."""
    data = to_data(result)
    lines = [
        f"code: {data.get('code')}",
        f"is_default: {data.get('is_default')}",
    ]
    if data.get("label"):
        lines.append(f"label: {data.get('label')}")
    sys.stdout.write("\n".join(lines) + "\n")


def emit_link_human(result: object) -> None:
    """Render a referral link result as human-readable key: value."""
    data = to_data(result)
    lines = [
        f"referral_code: {data.get('referral_code')}",
        f"link: {data.get('link')}",
    ]
    if data.get("course_id"):
        lines.append(f"course_id: {data.get('course_id')}")
    sys.stdout.write("\n".join(lines) + "\n")


def emit_stats_human(result: object) -> None:
    """Render referral statistics as human-readable key: value."""
    data = to_data(result)
    lines = [
        f"total_attributions: {data.get('total_attributions')}",
        f"active_attributions: {data.get('active_attributions')}",
        f"total_rewards_credited_cents: "
        f"{data.get('total_rewards_credited_cents')}",
        f"pending_rewards_cents: {data.get('pending_rewards_cents')}",
    ]
    sys.stdout.write("\n".join(lines) + "\n")


def emit_attributions_human(result: object) -> None:
    """Render referral attributions as human-readable entries."""
    items = to_data(result)
    if not items:
        sys.stdout.write("No referral attributions.\n")
    else:
        for item in items:
            lines = [
                f"id: {item.get('id')}",
                f"referrer_user_id: {item.get('referrer_user_id')}",
                f"referee_user_id: {item.get('referee_user_id')}",
                f"status: {item.get('status')}",
                f"signup_at: {item.get('signup_at')}",
                f"expires_at: {item.get('expires_at')}",
            ]
            sys.stdout.write("\n".join(lines) + "\n---\n")
