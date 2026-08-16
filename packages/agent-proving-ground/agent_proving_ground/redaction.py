from __future__ import annotations

import re

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
            if _is_sensitive_key(k, keys)
            else redact_json(v, keys, redact_emails)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact_json(v, keys, redact_emails) for v in value]
    if isinstance(value, str):
        text = redact_text(value)
        if redact_emails:
            text = _EMAIL_RE.sub(_REDACTED, text)
        return text
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
