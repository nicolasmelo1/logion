"""Example-based tests for companion workflows and references."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestCreatorCourseManagement:
    """Verify the creator course management reference."""

    def test_file_exists(self) -> None:
        assert (ROOT / "references" / "creator-course-management.md").is_file()

    def test_mentions_upload(self) -> None:
        content = (
            (ROOT / "references" / "creator-course-management.md")
            .read_text(encoding="utf-8")
            .lower()
        )
        assert "upload" in content, (
            "creator-course-management.md should mention upload"
        )

    def test_mentions_publish(self) -> None:
        content = (
            (ROOT / "references" / "creator-course-management.md")
            .read_text(encoding="utf-8")
            .lower()
        )
        assert "publish" in content, (
            "creator-course-management.md should mention publish"
        )
