# SPDX-License-Identifier: MIT
"""Constants for the ``logion instrument`` command.

Separated from ``parser.py`` to avoid a circular import between
``parser`` → ``handler`` → ``parser``.
"""

from __future__ import annotations

#: All supported projection targets.
TARGET_CHOICES: tuple[str, ...] = (
    "agent-plugin",
    "hermes-plugin",
    "static-skill",
    "dsh-plugin",
)

#: All supported event types for the instrumentation profile.
EVENT_CHOICES: tuple[str, ...] = (
    "resource_invoked",
    "resource_file_read",
    "resource_tool_used",
)

#: Delivery modes supported by the profile.
DELIVERY_MODE_CHOICES: tuple[str, ...] = ("asynchronous-batch",)
