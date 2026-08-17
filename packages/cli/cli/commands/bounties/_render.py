# SPDX-License-Identifier: MIT
"""Human-readable rendering for bounty and submission responses."""

from __future__ import annotations

from cli._json import JsonObject, opt_str


def github_pr_line(data: JsonObject) -> str:
    """Return a human-readable GitHub PR enabled line."""
    enabled = data.get("github_pr_enabled")
    return f"GitHub PRs: {'enabled' if enabled else 'disabled'}"


def fork_instructions(head_branch: str, *, indent: str = "") -> str:
    """Return the steps a contributor follows when a fork is required."""
    return (
        f"{indent}This repository requires a fork:\n"
        f"{indent}  1. Fork the repository on GitHub.\n"
        f"{indent}  2. Push your work to branch:\n"
        f"{indent}       {head_branch}\n"
        f"{indent}  3. Open a PR from your fork with the Logion marker "
        "in the body; Logion registers it automatically."
    )


def render_github_pr_block(block: JsonObject, *, indent: str = "  ") -> None:
    """Render the ``github_pr`` block returned by submissions create."""
    status = opt_str(block, "status", "")
    pr_url = opt_str(block, "pr_url", "")
    reason = opt_str(block, "reason", "")

    if status == "opened" and pr_url:
        print(f"{indent}PR opened: {pr_url}")
        return
    if status == "fork_required":
        print(
            fork_instructions(opt_str(block, "head_branch", ""), indent=indent)
        )
        pr_body = opt_str(block, "pr_body", "")
        if pr_body:
            print(f"\n{indent}Paste-ready PR body:\n{pr_body}")
        return
    # disabled / skipped / failed all carry a reason; anything else is a
    # status the CLI does not know about yet, shown verbatim.
    if status in {"disabled", "skipped", "failed"}:
        print(f"{indent}GitHub PR {status}: {reason}")
        return
    print(f"{indent}GitHub PR: {status}")
