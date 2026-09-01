from __future__ import annotations

import os
import re
from pathlib import Path

DEFAULT_SECRET_KEYWORDS = {
    "api_key",
    "apikey",
    "authorization",
    "bearer",
    "token",
    "secret",
    "password",
}

_TOKEN_LIKE_RE = re.compile(r"[A-Za-z0-9_\-]{16,}")
_BEARER_RE = re.compile(r"(?i)bearer\s+[a-z0-9_\-\.]{8,}")
# API keys use the lowercase ``logion_`` prefix. Keep this case-sensitive so
# harmless environment variable names such as ``LOGION_HOME_NATIVE`` do not
# become false positives in the timeline integrity check.
_API_KEY_RE = re.compile(r"logion_[a-z0-9_\-]{8,}")
_GITHUB_TOKEN_RE = re.compile(
    r"(?i)gh[pousr]_[a-z0-9_]{36,}|github[_-]?token[=:]\s*[a-z0-9]{35,}"
)
_STRIPE_KEY_RE = re.compile(r"(?i)(sk|pk)_(live|test)_[a-z0-9]{24,}")
_PROVIDER_KEY_RE = re.compile(
    r"(?i)(openai|anthropic|xai|groq|cohere)[_-]?key[=:]\s*[a-z0-9_\-]{16,}"
)
_SETUP_TOKEN_RE = re.compile(r"(?i)setup[_-]?token[=:]\s*[a-z0-9_\-]{8,}")
_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")

_REDACTED = "<redacted>"
_PRESENT_REDACTED = "<present:redacted>"


def _home_prefix() -> str:
    """The operator's home directory, or "" when it cannot be resolved."""
    try:
        return str(Path.home())
    except (OSError, RuntimeError):  # pragma: no cover - no HOME set
        return ""


def normalize_home_paths(value: str) -> str:
    """Rewrite absolute paths under the operator's home to ``~``.

    Retained evidence is committed to a public repository, where an
    operator's real home directory is both a privacy leak and a portability
    problem: a reader cannot tell which parts of a path are meaningful. The
    guardrail in ``scripts/audit_public_safe.py`` refuses host paths for
    exactly this reason, so reports stop producing them at the source
    rather than accumulating allowlist entries for each new run.

    This is deliberately *not* part of :func:`redact_text`. That function
    is also the detector behind ``timeline.no_unredacted_secret``, which
    asserts it leaves an already-clean line untouched; a cosmetic rewrite
    in there reports every local path as an unredacted secret.
    """
    home = _home_prefix()
    if not home or home in {"/", os.sep}:
        return value
    return value.replace(home, "~")


def redact_text(value: str, extra_patterns: list[str] | None = None) -> str:
    text = value
    text = _BEARER_RE.sub("bearer " + _REDACTED, text)
    text = _API_KEY_RE.sub(_REDACTED, text)
    text = _GITHUB_TOKEN_RE.sub(_REDACTED, text)
    text = _STRIPE_KEY_RE.sub(_REDACTED, text)
    text = _PROVIDER_KEY_RE.sub(_REDACTED, text)
    text = _SETUP_TOKEN_RE.sub(_REDACTED, text)
    if extra_patterns:
        for pattern in extra_patterns:
            text = re.sub(pattern, _REDACTED, text)
    return text


#: Shortest string the key heuristic will redact. Real credentials are
#: long: the shortest thing this repo issues is a 14-character prefix plus
#: 43 random characters. Below this, a sensitive-looking key is far more
#: likely to be naming a subject than holding a secret.
_CREDENTIAL_MIN_LEN = 16


def _cannot_be_secret(value: object) -> bool:
    """True for values that carry no secret no matter what they are named.

    The key heuristic is a backstop for values that no pattern matches. It
    misfires on facts keyed by what they are *about* rather than by what
    they hold: ``{"coordinator_token": false}`` says a canary was not
    readable, and ``{"secret_read": "failed"}`` is a terminal status.
    Replacing those protects nothing and destroys the observation the
    auditor recomputes its verdict from.

    Narrowing this backstop does not narrow the real control: every string
    still goes through :func:`redact_text`, so anything shaped like a
    bearer token, API key, GitHub, Stripe or provider credential is
    redacted on its own evidence regardless of the key it sits under.
    """
    if value is None or isinstance(value, bool):
        return True
    return isinstance(value, str) and len(value) < _CREDENTIAL_MIN_LEN


def redact_json(
    value: object,
    sensitive_keys: set[str] | None = None,
    redact_emails: bool = False,
) -> object:
    """Return *value* with secrets in its strings replaced.

    Takes ``object`` rather than ``JsonValue`` because the artifact
    store also passes trees containing ``Path``, which its
    ``json.dumps`` default hook renders later. Everything it does
    not recognise is returned untouched.
    """
    keys = (sensitive_keys or set()) | DEFAULT_SECRET_KEYWORDS
    if isinstance(value, dict):
        return {
            k: _REDACTED
            if _is_sensitive_key(k, keys) and not _cannot_be_secret(v)
            else redact_json(v, keys, redact_emails)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact_json(v, keys, redact_emails) for v in value]
    if isinstance(value, str):
        text = redact_text(value)
        if redact_emails:
            text = _EMAIL_RE.sub(_REDACTED, text)
        # Structured evidence is what gets sealed into a public repo, so
        # it is normalized here rather than in `redact_text`: that
        # function doubles as the secret *detector*
        # (`timeline.no_unredacted_secret` asserts it changes nothing),
        # and anything cosmetic inside it reads as a leak.
        return normalize_home_paths(text)
    return value


def redact_env(
    env: dict[str, str], sensitive_keys: set[str] | None = None
) -> dict[str, str]:
    keys = (sensitive_keys or set()) | DEFAULT_SECRET_KEYWORDS
    return {
        k: _PRESENT_REDACTED if _is_sensitive_key(k, keys) else v
        for k, v in env.items()
    }


def _is_sensitive_key(key: str, keys: set[str]) -> bool:
    lowered = key.lower().replace("-", "_")
    return lowered in keys or any(suffix in lowered for suffix in keys)
