"""OAuth token handling for the bundled Gmail CLI.

The course does not implement the OAuth dance. The user obtains a
token externally (via the Google OAuth playground or their own auth
flow) and exports it as GMAIL_OAUTH_TOKEN before invoking the course.

This is the trust-clean pattern: token acquisition is the user's
separate consent decision, outside Logion's trust loop. Logion's
capability manifest declares GMAIL_OAUTH_TOKEN as a secret the course
is allowed to read. Nothing else.
"""

from __future__ import annotations

import os


class MissingTokenError(Exception):
    """Raised when GMAIL_OAUTH_TOKEN is not set in the environment."""


def get_oauth_token() -> str:
    token = os.environ.get("GMAIL_OAUTH_TOKEN", "").strip()
    if not token:
        raise MissingTokenError(
            "GMAIL_OAUTH_TOKEN environment variable is not set. "
            "Obtain a token via the Google OAuth playground "
            "(https://developers.google.com/oauthplayground) and "
            "export it before invoking this course."
        )
    return token
