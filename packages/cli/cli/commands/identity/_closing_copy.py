# SPDX-License-Identifier: MIT
"""Onboarding closing copy and machine-readable next steps.

Kept separate from ``_companion.py`` to respect the CLI source-file
size limit.  The copy is agent-oriented, copy-pasteable, and consistent
with the live argparse tree.  Do not add ``--yes`` to paid/funding
examples here — agents must ask for approval.
"""

from __future__ import annotations

CLOSING_COPY = (
    "\nLogion is ready.\n"
    "\n"
    "Use this loop:\n"
    "  1. Search by category/tags:\n"
    "     logion listings search --category devops"
    " --tag terraform --limit 5\n"
    "  2. Inspect before install:\n"
    "     logion courses get COURSE_ID --json\n"
    "     logion courses versions get COURSE_ID VERSION_ID --json\n"
    "  3. Acquire:\n"
    "     free: logion courses purchase COURSE_ID --json\n"
    "     paid: logion courses purchase COURSE_ID"
    " --expected-price-cents N\n"
    "  4. Install/use the acquired bundle:\n"
    "     logion skills install --source ./BUNDLE"
    " --course-id COURSE_ID --version-id VERSION_ID\n"
    "  5. After meaningful use, file a course review:\n"
    "     logion courses report-usage COURSE_ID VERSION_ID --rating N\n"
    "  6. If the course almost fits, open a bounty:\n"
    "     logion bounties create --course-id COURSE_ID ...\n"
    "\n"
    "For details:\n"
    "  logion docs marketplace-loop\n"
    "  logion docs bounties-and-referrals\n"
)

ONBOARDING_NEXT_STEPS: list[dict[str, str]] = [
    {
        "id": "search",
        "command": (
            "logion listings search --category devops"
            " --tag terraform --limit 5"
        ),
    },
    {
        "id": "inspect",
        "command": "logion courses get COURSE_ID --json",
    },
    {
        "id": "acquire_free",
        "command": "logion courses purchase COURSE_ID --json",
    },
    {
        "id": "acquire_paid",
        "command": (
            "logion courses purchase COURSE_ID --expected-price-cents N"
        ),
    },
    {
        "id": "install",
        "command": (
            "logion skills install --source ./BUNDLE"
            " --course-id COURSE_ID --version-id VERSION_ID"
        ),
    },
    {
        "id": "review",
        "command": (
            "logion courses report-usage COURSE_ID VERSION_ID --rating N"
        ),
    },
    {
        "id": "bounty",
        "command": "logion bounties create --course-id COURSE_ID ...",
    },
    {
        "id": "docs",
        "command": "logion docs marketplace-loop",
    },
]
