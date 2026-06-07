# SPDX-License-Identifier: MIT
"""Shared helpers for referrals commands."""

from __future__ import annotations

import sys

from cli._output import to_data


def emit_code_human(result: object) -> None:
    """Render a referral code result as human-readable key: value."""
    data = to_data(result)
    lines = [
        f"referral_code: {data.get('referral_code')}",
    ]
    sys.stdout.write("\n".join(lines) + "\n")


def emit_link_human(result: object) -> None:
    """Render a referral link result as human-readable key: value."""
    data = to_data(result)
    lines = [
        f"course_id: {data.get('course_id')}",
        f"referral_link: {data.get('referral_link')}",
    ]
    sys.stdout.write("\n".join(lines) + "\n")


def emit_stats_human(result: object) -> None:
    """Render referral statistics as human-readable key: value."""
    data = to_data(result)
    lines = [
        f"total_referrals: {data.get('total_referrals')}",
        f"product_lane: {data.get('product_lane')}",
        f"creator_lane: {data.get('creator_lane')}",
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
                f"referred_user_id: {item.get('referred_user_id')}",
                f"lane: {item.get('lane')}",
                f"attributed_at: {item.get('attributed_at')}",
            ]
            sys.stdout.write("\n".join(lines) + "\n---\n")
