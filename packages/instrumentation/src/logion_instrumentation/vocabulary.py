# SPDX-License-Identifier: MIT
"""Vocabulary bridge — the single source of truth for enum values.

These tuples are copied verbatim from
``packages/cli/cli/usage/observations.py`` (``EVENT_VALUES``,
``OUTCOME_VALUES``, ``DURATION_BUCKETS``) so this package stays
self-contained and never imports the CLI.

A grep-pinned test (``test_vocabulary_pin.py``) asserts that the values
here match the CLI source line-for-line, preventing a second divergent
vocabulary set from silently drifting.
"""

from __future__ import annotations

#: Events the instrumentation profile may declare.
#: Mirrors ``EVENT_VALUES`` in ``cli/usage/observations.py``.
EVENT_VALUES: tuple[str, ...] = (
    "resource_invoked",
    "resource_file_read",
    "resource_tool_used",
)

#: Outcomes the instrumentation profile may declare.
#: Mirrors ``OUTCOME_VALUES`` in ``cli/usage/observations.py``.
OUTCOME_VALUES: tuple[str, ...] = (
    "completed",
    "failed",
    "abandoned",
    "unknown",
)

#: Duration buckets the instrumentation profile may declare.
#: Mirrors ``DURATION_BUCKETS`` in ``cli/usage/observations.py``.
#: Sorted here for deterministic schema generation; the CLI source is a
#: frozenset so order is not significant there.
DURATION_BUCKET_VALUES: tuple[str, ...] = (
    "hours",
    "instant",
    "minutes",
    "seconds",
    "unknown",
)

#: Allowed field names in the ``fields`` array.
ALLOWED_FIELD_NAMES: frozenset[str] = frozenset({
    "resource_id",
    "resource_version",
    "distribution_digest",
    "event",
    "outcome",
    "duration_bucket",
    "harness",
    "integration_version",
})

#: Fields that must appear in the ``excluded`` array if sensitive data
#: categories are to be blocked.  The validator does not require all of
#: them, but the diff mode flags when a new version *removes* one.
SENSITIVE_EXCLUDED_FIELDS: frozenset[str] = frozenset({
    "prompt",
    "file_content",
    "local_path",
    "tool_arguments",
    "tool_results",
    "model_context",
    "secrets",
    "user_identity",
})

#: Maximum byte length for a single string field value.
MAX_FIELD_BYTES = 4096

#: Maximum byte length for the entire profile payload.
MAX_PAYLOAD_BYTES = 131072

#: Maximum number of events in the ``events`` array.
MAX_EVENTS = 32

#: Maximum number of fields in the ``fields`` array.
MAX_FIELDS = 32

#: Maximum number of entries in the ``excluded`` array.
MAX_EXCLUDED = 64

#: Delivery modes the profile supports.
DELIVERY_MODES: tuple[str, ...] = ("asynchronous-batch",)
