# SPDX-License-Identifier: MIT
"""Browser-launch helpers for the GitHub device flow.

Kept separate from ``github.py`` so the command handler stays under the
per-file line budget enforced by the architecture test.
"""

from __future__ import annotations

from urllib.parse import quote


def completion_uri(
    begin: object, verification_uri: str, user_code: str
) -> str:
    """Return the best URL to open for authorization.

    Prefers ``verification_uri_complete`` (the device-flow field that
    embeds the code so the browser page is pre-filled) when the API
    returns it, otherwise appends ``?user_code=`` to the base
    verification URI so the user still lands on a pre-filled page.
    """
    complete = getattr(begin, "verification_uri_complete", None)
    if isinstance(complete, str) and complete:
        return complete
    sep = "&" if "?" in verification_uri else "?"
    return f"{verification_uri}{sep}user_code={quote(user_code)}"


def try_open_browser(url: str) -> bool:
    """Best-effort open *url* in the user's browser; never raise.

    Returns ``True`` only if a browser was actually launched, so callers
    can fall back to printing copy-paste instructions when it did not.
    """
    try:
        import webbrowser

        # ``new=2`` asks for a new tab when a browser is already running.
        return webbrowser.open(url, new=2)
    except Exception:
        return False


def device_prompt_line(
    begin: object,
    verification_uri: str,
    user_code: str,
    *,
    no_browser: bool,
    is_tty: bool,
) -> str:
    """Return the human-facing device-flow instruction line.

    Auto-launches the browser only for an interactive human at a terminal
    (``is_tty`` and not ``no_browser``); a no-TTY invocation (agent/CI) or
    an explicit ``--no-browser`` falls back to copy-paste instructions.
    """
    opened = False
    if not no_browser and is_tty:
        opened = try_open_browser(
            completion_uri(begin, verification_uri, user_code)
        )
    if opened:
        return (
            f"Opened {verification_uri} in your browser. "
            f"Confirm this code is shown: {user_code}"
        )
    return f"Open {verification_uri} and enter code: {user_code}"
