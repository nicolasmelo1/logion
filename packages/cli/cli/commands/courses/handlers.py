# SPDX-License-Identifier: MIT
"""Stable handler exports for courses commands."""

from ._purchase import handle_purchase
from .capabilities import (
    handle_courses_capabilities_print,
    handle_courses_capabilities_validate,
)
from .listing import handle_mine
from .mutations import (
    handle_create,
    handle_get,
    handle_update,
)
from .publication import (
    handle_publication_latest,
    handle_publication_request,
)
from .report_usage import handle_report_usage
from .reviews import (
    handle_feedback,
    handle_reviews_list,
    handle_reviews_mine,
    handle_reviews_summary,
    handle_reviews_upsert,
)
from .uploads import (
    handle_uploads_complete,
    handle_uploads_create,
)
from .versions import handle_versions_get

__all__ = [
    "handle_courses_capabilities_print",
    "handle_courses_capabilities_validate",
    "handle_create",
    "handle_feedback",
    "handle_get",
    "handle_mine",
    "handle_publication_latest",
    "handle_publication_request",
    "handle_purchase",
    "handle_report_usage",
    "handle_reviews_list",
    "handle_reviews_mine",
    "handle_reviews_summary",
    "handle_reviews_upsert",
    "handle_update",
    "handle_uploads_complete",
    "handle_uploads_create",
    "handle_versions_get",
]
