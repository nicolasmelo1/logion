# SPDX-License-Identifier: MIT
"""Canonical inventory for the reference-routing signature.

Kept dspy-free so tests + scenario loaders can import it without the
optional optimisation dependency.
"""

from __future__ import annotations

# Single source of truth for the 10-class output enum.  The Literal
# in ``reference_routing.py`` (which requires dspy) MUST match this
# tuple exactly; ``test_reference_routing.py`` asserts the parity.
REFERENCE_NAMES: tuple[str, ...] = (
    "none",
    "creator-course-management",
    "account-and-identity",
    "notifications-and-reports",
    "credits-and-payments",
    "bounties",
    "course-review-queue",
    "admin-operations",
    "troubleshooting",
    "referrals",
)
