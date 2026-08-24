# SPDX-License-Identifier: MIT
"""Minimal JSON value types for the instrumentation package.

Keeps the package self-contained — no dependency on the CLI's ``_json``
module.  ``JsonValue`` is intentionally ``object``: a profile is loaded
from a JSON file so the exact runtime shape is only known at load time,
and narrowing happens at the point of use.
"""

from __future__ import annotations

#: A JSON value loaded from a file.
JsonValue = object

#: A JSON object (dictionary).
JsonObject = dict[str, JsonValue]
