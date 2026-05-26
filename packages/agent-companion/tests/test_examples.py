"""Example-based tests for companion workflows and references.

Verifies that the reference documentation files contain the
required sections and that references are well-formed.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class TestMarketplaceFlows:
    """Verify the marketplace flows reference."""

    def test_file_exists(self) -> None:
        assert (ROOT / "references" / "marketplace-flows.md").is_file()

    def test_mentions_local_recall(self) -> None:
        content = (
            (ROOT / "references" / "marketplace-flows.md")
            .read_text(encoding="utf-8")
            .lower()
        )
        assert "recall" in content, (
            "marketplace-flows.md should mention local recall"
        )

    def test_mentions_confirmation(self) -> None:
        content = (
            (ROOT / "references" / "marketplace-flows.md")
            .read_text(encoding="utf-8")
            .lower()
        )
        assert "confirm" in content, (
            "marketplace-flows.md should mention confirmation"
        )


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


class TestSafetyAndApproval:
    """Verify the safety and approval reference."""

    def test_file_exists(self) -> None:
        assert (ROOT / "references" / "safety-and-approval.md").is_file()

    def test_lists_confirmation_actions(self) -> None:
        content = (ROOT / "references" / "safety-and-approval.md").read_text(
            encoding="utf-8"
        )
        for action in [
            "paid_checkout",
            "install_new_capability",
            "publish_or_unpublish_course",
        ]:
            assert action in content, (
                f"safety-and-approval.md should list {action}"
            )

    def test_local_recall_read_only(self) -> None:
        content = (
            (ROOT / "references" / "safety-and-approval.md")
            .read_text(encoding="utf-8")
            .lower()
        )
        assert "read-only" in content or "never execute" in content, (
            "safety-and-approval.md should state local recall is read-only"
        )


class TestLowContextLoading:
    """Verify the low context loading reference."""

    def test_file_exists(self) -> None:
        assert (ROOT / "references" / "low-context-loading.md").is_file()

    def test_mentions_bootstrap(self) -> None:
        content = (
            (ROOT / "references" / "low-context-loading.md")
            .read_text(encoding="utf-8")
            .lower()
        )
        assert "bootstrap" in content, (
            "low-context-loading.md should mention bootstrap"
        )

    def test_mentions_recall_first(self) -> None:
        content = (
            (ROOT / "references" / "low-context-loading.md")
            .read_text(encoding="utf-8")
            .lower()
        )
        recall_pos = content.find("recall")
        search_pos = content.find("marketplace")
        if recall_pos >= 0 and search_pos >= 0:
            assert recall_pos < search_pos, (
                "low-context-loading.md should "
                "mention recall before marketplace "
                "search"
            )
