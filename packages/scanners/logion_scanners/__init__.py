"""Logion Scanners — deterministic course-scanning engine."""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = [  # noqa: F822
    "AgentScanner",
    "BaseScanner",
    "OsvScanner",
    "ScanPolicy",
    "ScannerFinding",
    "ScannerResult",
    "TrivyScanner",
]


def __getattr__(name: str):  # type: ignore[no-untyped-def]
    """Lazy imports to avoid circular dependency at module load time."""
    if name == "AgentScanner":
        from logion_scanners.adapters.agent import AgentScanner

        return AgentScanner
    if name == "BaseScanner":
        from logion_scanners.adapters.base import BaseScanner

        return BaseScanner
    if name == "TrivyScanner":
        from logion_scanners.adapters.trivy import TrivyScanner

        return TrivyScanner
    if name == "OsvScanner":
        from logion_scanners.adapters.osv import OsvScanner

        return OsvScanner
    if name == "ScanPolicy":
        from logion_scanners.models import ScanPolicy

        return ScanPolicy
    if name == "ScannerResult":
        from logion_scanners.models import ScannerResult

        return ScannerResult
    if name == "ScannerFinding":
        from logion_scanners.models import ScannerFinding

        return ScannerFinding
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
