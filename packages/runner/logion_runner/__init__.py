"""Reference isolated runner node for Logion."""

__all__ = ["package_version"]


def package_version() -> str:
    """Return the installed package version, "unknown" when unavailable."""
    from importlib import metadata

    try:
        return metadata.version("logion-runner")
    except Exception:
        return "unknown"
