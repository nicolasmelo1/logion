"""Base scanner abstract class."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from logion_scanners.models import ScannerResult


class BaseScanner(ABC):
    """Base class for all review scanners."""

    layer: str  # subclass must set e.g. "trivy"

    @abstractmethod
    def scan(self, bundle_path: Path) -> ScannerResult:
        """Scan a course bundle directory and return results."""
        ...
