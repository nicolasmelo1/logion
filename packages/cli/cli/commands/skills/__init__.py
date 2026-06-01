# SPDX-License-Identifier: MIT
"""Skills command package — local install/update/inspect of marketplace
capabilities under ``~/.logion/installed``."""

from .parser import register

__all__ = ["register"]
