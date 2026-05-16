"""Stable handler exports for courses commands."""

from .mutations import (
    handle_create,
    handle_get,
    handle_update,
)
from .publication import (
    handle_publication_latest,
    handle_publication_request,
)
from .reviews import (
    handle_feedback,
    handle_reviews_list,
    handle_reviews_mine,
    handle_reviews_upsert,
)
from .uploads import (
    handle_uploads_complete,
    handle_uploads_create,
)
from .versions import handle_versions_get

__all__ = [
    "handle_create",
    "handle_feedback",
    "handle_get",
    "handle_publication_latest",
    "handle_publication_request",
    "handle_reviews_list",
    "handle_reviews_mine",
    "handle_reviews_upsert",
    "handle_update",
    "handle_uploads_complete",
    "handle_uploads_create",
    "handle_versions_get",
]
