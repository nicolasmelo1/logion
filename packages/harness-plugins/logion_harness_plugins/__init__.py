# SPDX-License-Identifier: MIT
"""Logion observer plugin — thin harness hooks for use observation.

This package installs lifecycle hooks into supported harnesses (Claude
Code, Codex).  It delegates identity, inventory resolution, consent,
spool, redaction, and API writes to the verified Logion CLI.  It does
not bundle API secrets, duplicate CLI logic, or silently opt the user
into upload.

The hook exits 0 on any failure so it never breaks the harness.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
