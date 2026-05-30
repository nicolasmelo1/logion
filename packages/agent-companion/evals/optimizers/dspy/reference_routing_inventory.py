"""Phase 6.11: canonical inventory for the reference-routing
signature.  Kept dspy-free so tests + scenario loaders can import
it without the optional optimisation dependency.
"""

from __future__ import annotations

# Single source of truth for the 9-class output enum.  The Literal
# in ``reference_routing.py`` (which requires dspy) MUST match this
# tuple exactly; ``test_reference_routing.py`` asserts the parity.
REFERENCE_NAMES: tuple[str, ...] = (
    "none",
    "creator-course-management",
    "account-and-identity",
    "notifications-and-reports",
    "payments-and-checkout",
    "bounties",
    "course-review-queue",
    "admin-operations",
    "troubleshooting",
)
