# SPDX-License-Identifier: MIT
"""Instrument command package — ``logion instrument`` generator.

Produces a projection directory from a canonical ResourceVersion, with
an instrumentation profile, capability.json, and per-target projection
trees.  The generator copies the portable core byte-identical, computes
digests, and produces a reviewable plan before any write.
"""

from .parser import register

__all__ = ["register"]
