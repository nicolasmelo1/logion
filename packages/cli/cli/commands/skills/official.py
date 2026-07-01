# SPDX-License-Identifier: MIT
"""Official companion service for status, install, and update."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from cli._first_party import LOGION_MARKETPLACE_COMPANION_COURSE_ID
from cli._local_state import get_home, list_installed


@dataclass(frozen=True)
class CompanionInstallStatus:
    """Status of the official companion installation."""

    installed: bool
    course_id: str
    version_id: str | None
    version: str | None
    source: str | None
    needs_update: bool
    reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "installed": self.installed,
            "course_id": self.course_id,
            "version_id": self.version_id,
            "version": self.version,
            "source": self.source,
            "needs_update": self.needs_update,
            "reason": self.reason,
        }


class OfficialCompanionService:
    """Inspect and manage the first-party companion installation."""

    def __init__(
        self,
        home: Path | None = None,
        manifest_data: dict[str, Any] | None = None,
    ) -> None:
        self._home = home or get_home()
        self._manifest = manifest_data

    def inspect(self) -> CompanionInstallStatus:
        """Check if the companion is installed and report status."""
        installed = list_installed(self._home)
        for entry in installed:
            if (
                entry.get("course_id")
                == LOGION_MARKETPLACE_COMPANION_COURSE_ID
            ):
                return CompanionInstallStatus(
                    installed=True,
                    course_id=LOGION_MARKETPLACE_COMPANION_COURSE_ID,
                    version_id=entry.get("version_id"),
                    version=entry.get("version", entry.get("version_id")),
                    source=entry.get("source"),
                    needs_update=False,
                    reason=None,
                )
        return CompanionInstallStatus(
            installed=False,
            course_id=LOGION_MARKETPLACE_COMPANION_COURSE_ID,
            version_id=None,
            version=None,
            source=None,
            needs_update=True,
            reason=(
                "Companion not installed. Run: "
                "logion skills companion install --channel stable"
            ),
        )

    def install_from_manifest(
        self,
        manifest: dict[str, Any],
    ) -> CompanionInstallStatus:
        """Install companion from a release manifest dict."""
        companion_entry = manifest.get("packages", {}).get(
            "logion-companion", {}
        )
        version = companion_entry.get("version")
        course_id = companion_entry.get(
            "course_id",
            LOGION_MARKETPLACE_COMPANION_COURSE_ID,
        )
        if not version:
            return CompanionInstallStatus(
                installed=False,
                course_id=course_id,
                version_id=None,
                version=None,
                source=None,
                needs_update=True,
                reason="Manifest missing companion version",
            )
        status = self.inspect()
        if status.installed and status.version == version:
            return status
        return CompanionInstallStatus(
            installed=False,
            course_id=course_id,
            version_id=version,
            version=version,
            source="manifest",
            needs_update=True,
            reason=("Run: logion skills companion install --channel stable"),
        )

    def install_from_marketplace(
        self,
        version_id: str | None = None,
    ) -> CompanionInstallStatus:
        """Install companion from the marketplace API."""
        return CompanionInstallStatus(
            installed=False,
            course_id=LOGION_MARKETPLACE_COMPANION_COURSE_ID,
            version_id=version_id,
            version=version_id,
            source="marketplace",
            needs_update=True,
            reason="Marketplace install requires API connection",
        )
