"""Constants for the cost domain.

Pricing constants reflect X pay-per-use as researched Jun 2026.
"""

from __future__ import annotations

import re

POST_COST_CENTS = 2  # ~$0.015 rounded up to 2c
POST_WITH_LINK_COST_CENTS = 20  # ~$0.20 link tax
READ_COST_CENTS = 1  # ~$0.005 rounded up; reads are not gated, FYI

# Matches http(s):// and bare domains likely to be unfurled by X.
URL_RE = re.compile(
    r"(https?://\S+|\bwww\.\S+|\b[a-z0-9.-]+\.(?:com|sh|io|org|net|dev)\b)",
    re.IGNORECASE,
)
