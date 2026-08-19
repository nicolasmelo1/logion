# SPDX-License-Identifier: MIT
"""Shared validation primitives for the observation envelope.

Only the opaque-identifier and slug regexes are imported by
``cli.usage.observations``.  The richer validation helpers that used to
live here were consumed by the consolidated ``UsageObservation`` dataclass
when ``cli._observation`` was deleted; the field-level checks now live
inline on the dataclass itself.
"""

from __future__ import annotations

import re

OPAQUE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
