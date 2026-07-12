# SPDX-License-Identifier: MIT
"""Pinned reply templates for the issue-mention bounty bot.

All amounts are credits. No template in this module renders a dollar sign or
uses the three-letter fiat currency code.
"""

from __future__ import annotations


def reply_ask_amount(*, bot: str, ttl_hours: int) -> str:
    return (
        "Hi! To open a bounty, please include the amount in credits.\n\n"
        f"Example: `@{bot} bounty 250`\n\n"
        "Accepted format: a whole number of credits between 1 and "
        "9,999,999.\n"
        f"Threads expire after {ttl_hours} hours if not confirmed."
    )


def reply_confirm_prompt(
    *,
    bot: str,
    amount_credits: int,
    course_title: str,
    ttl_hours: int,
) -> str:
    return (
        f"Open a bounty on **{course_title}** for "
        f"**{amount_credits} credits**?\n"
        f"This will debit {amount_credits} credits from your Logion "
        "balance.\n\n"
        f"To confirm: `@{bot} confirm`\n"
        f"To cancel: `@{bot} cancel`\n\n"
        f"Threads expire after {ttl_hours} hours if not confirmed."
    )


def reply_opened(*, bounty_url: str, amount_credits: int) -> str:
    return (
        "Bounty opened and funded with "
        f"{amount_credits} credits:\n{bounty_url}"
    )


def reply_opened_unfunded(*, bounty_url: str, bounty_id: str) -> str:
    return (
        "Bounty is open but unfunded — your Logion balance does not have "
        "enough credits.\n"
        f"{bounty_url}\n\n"
        "Top up at https://logion.sh, then fund it with:\n"
        f"`logion bounties fund {bounty_id} --yes`"
    )


def reply_open_failed(*, error_code: str) -> str:
    return (
        f"Could not open the bounty ({error_code}). Nothing was funded. "
        "Please try again or contact support."
    )


def reply_already_opened(*, bounty_url: str) -> str:
    return f"A bounty is already open for this issue:\n{bounty_url}"


def reply_nothing_to_confirm(*, bot: str) -> str:
    return f"There is nothing to confirm. Start with `@{bot} bounty <amount>`."


def reply_confirm_wrong_user(*, login: str) -> str:
    return f"Only @{login} (who proposed the bounty) can confirm it."


def reply_cancelled() -> str:
    return "Bounty thread cancelled. Start over with a new bounty command."


def reply_nothing_to_cancel() -> str:
    return "There is no active bounty thread to cancel."


def reply_help(*, bot: str) -> str:
    return (
        f"`@{bot} bounty <amount>` — propose a bounty (amount in credits)\n"
        f"`@{bot} confirm`         — confirm the proposed bounty\n"
        f"`@{bot} cancel`          — cancel the active thread\n"
        f"`@{bot} help`            — show this help"
    )


def reply_refused_repo_not_linked() -> str:
    return (
        "This repository is not linked to a Logion course. Link it first "
        "with `logion courses link`."
    )


def reply_refused_course_ambiguous(*, slugs: list[str] | None = None) -> str:
    names = ", ".join(f"`{s}`" for s in slugs or [])
    if names:
        return (
            f"This repository is linked to multiple courses: {names}. "
            "Pick one by adding `course:<slug>` to the bounty command."
        )
    return (
        "This repository is linked to multiple courses. Pick one by "
        "adding `course:<slug>` to the bounty command."
    )


def reply_refused_course_slug_not_found(
    *,
    slug: str | None = None,
    slugs: list[str] | None = None,
) -> str:
    names = ", ".join(f"`{s}`" for s in slugs or [])
    head = (
        f"No linked course matches `{slug}`."
        if slug
        else "The requested course is not linked to this repository."
    )
    if names:
        return f"{head} Available: {names}."
    return head


def reply_refused_course_not_published() -> str:
    return "The linked course is not published, so no bounty can be opened."


def reply_refused_author_not_linked() -> str:
    return (
        "Your GitHub account is not linked to a Logion identity. "
        "Link it with `logion auth`."
    )


def reply_refused_not_owner() -> str:
    return (
        "Only the course owner can open a creator-funded bounty from an issue."
    )
