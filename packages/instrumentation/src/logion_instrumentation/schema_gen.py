# SPDX-License-Identifier: MIT
"""Build the ``logion.instrumentation/v1`` JSON Schema at runtime.

The schema is generated from :mod:`logion_instrumentation.vocabulary`
so enum values are always in sync with the CLI source.  The generated
dict is also written to
``src/logion_instrumentation/schema/logion.instrumentation.v1.json``
for tooling that prefers a static file; both paths produce the same
object.
"""

from __future__ import annotations

from logion_instrumentation._json import JsonObject
from logion_instrumentation.vocabulary import (
    ALLOWED_FIELD_NAMES,
    DELIVERY_MODES,
    EVENT_VALUES,
    MAX_EVENTS,
    MAX_EXCLUDED,
    MAX_FIELD_BYTES,
    MAX_FIELDS,
    SENSITIVE_EXCLUDED_FIELDS,
)

SCHEMA_ID = "logion.instrumentation/v1"
SCHEMA_BASE = "https://logion.sh/schemas/"
SCHEMA_ID_URL = SCHEMA_BASE + SCHEMA_ID


def build_schema() -> JsonObject:
    """Return the v1 instrumentation profile JSON Schema as a dict."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": SCHEMA_ID_URL,
        "title": "Logion Instrumentation Profile",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema",
            "subject",
            "publisher",
            "delivery",
            "events",
            "fields",
            "excluded",
            "integration_version",
        ],
        "properties": {
            "schema": {
                "type": "string",
                "const": SCHEMA_ID,
            },
            "subject": {
                "type": "object",
                "additionalProperties": False,
                "required": ["resource_id", "resource_version"],
                "properties": {
                    "resource_id": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": MAX_FIELD_BYTES,
                    },
                    "resource_version": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": MAX_FIELD_BYTES,
                    },
                    "distribution_digest": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": MAX_FIELD_BYTES,
                    },
                },
            },
            "publisher": {
                "type": "object",
                "additionalProperties": False,
                "required": ["identity"],
                "properties": {
                    "identity": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": MAX_FIELD_BYTES,
                    },
                },
            },
            "delivery": {
                "type": "object",
                "additionalProperties": False,
                "required": ["endpoint", "mode", "max_batch"],
                "properties": {
                    "endpoint": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": MAX_FIELD_BYTES,
                    },
                    "mode": {
                        "type": "string",
                        "enum": list(DELIVERY_MODES),
                    },
                    "max_batch": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 1000,
                    },
                    "max_spool_bytes": {
                        "type": "integer",
                        "minimum": 1024,
                        "maximum": 1048576,
                    },
                },
            },
            "events": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_EVENTS,
                "items": {
                    "type": "string",
                    "enum": list(EVENT_VALUES),
                },
            },
            "fields": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_FIELDS,
                "items": {
                    "type": "string",
                    "enum": sorted(ALLOWED_FIELD_NAMES),
                },
            },
            "excluded": {
                "type": "array",
                "minItems": 1,
                "maxItems": MAX_EXCLUDED,
                "items": {
                    "type": "string",
                    "enum": sorted(SENSITIVE_EXCLUDED_FIELDS),
                },
            },
            "integration_version": {
                "type": "string",
                "minLength": 1,
                "maxLength": MAX_FIELD_BYTES,
            },
        },
    }


def build_endpoint_pattern() -> str:
    """Return a regex that matches HTTPS URLs with no template placeholders.

    A template endpoint containing ``RESOURCE_UUID`` or ``VERSION_UUID``
    will not match because those are not valid URL path segments in a
    resolved endpoint.
    """
    return (
        r"^https://"
        r"[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?"
        r"(\.[a-zA-Z0-9]([a-zA-Z0-9\-]*[a-zA-Z0-9])?)*"
        r"(:[0-9]+)?"
        r"(/[^\s]*)?$"
    )
