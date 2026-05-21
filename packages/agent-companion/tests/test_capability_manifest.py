"""Tests for the course/capabilities.yaml manifest.

Verifies the capability manifest has the required structure,
safety rules, local recall capability, and creator/operator
workflows.
"""

from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CAP_PATH = ROOT / "course" / "capabilities.yaml"

REQUIRED_CAPABILITY_IDS = [
    "logion.recall.search",
    "logion.marketplace.search",
    "logion.course.inspect",
    "logion.skill.install",
    "logion.skill.update",
    "logion.course.author",
    "logion.course.operate",
]

REQUIRED_CONFIRMATION_ACTIONS = [
    "paid_checkout",
    "install_new_capability",
    "update_paid_capability",
    "permission_expansion",
    "publish_or_unpublish_course",
    "upload_new_course_version",
    "change_course_price",
]


def _load_manifest() -> dict:
    content = CAP_PATH.read_text(encoding="utf-8")
    return yaml.safe_load(content)


class TestCapabilityManifest:
    """Verify the capability manifest has required fields."""

    def test_manifest_file_exists(self) -> None:
        assert CAP_PATH.is_file(), f"Missing manifest: {CAP_PATH}"

    def test_manifest_has_required_top_level_keys(
        self,
    ) -> None:
        data = _load_manifest()
        required = [
            "version",
            "summary",
            "capabilities",
            "required_tools",
            "safety",
        ]
        for key in required:
            assert key in data, f"Manifest missing key: {key}"

    def test_manifest_version_is_integer(self) -> None:
        data = _load_manifest()
        assert isinstance(data["version"], int), "Manifest version must be int"
        assert data["version"] >= 1, "Manifest version must be >= 1"

    def test_manifest_summary_is_nonempty(self) -> None:
        data = _load_manifest()
        assert isinstance(data["summary"], str), "Summary must be a string"
        assert len(data["summary"].strip()) > 0, "Summary must not be empty"

    def test_manifest_has_all_required_capabilities(
        self,
    ) -> None:
        data = _load_manifest()
        caps = data.get("capabilities", [])
        cap_ids = [c.get("id", "") for c in caps]
        for req_id in REQUIRED_CAPABILITY_IDS:
            assert req_id in cap_ids, (
                f"Manifest missing required capability: {req_id}"
            )

    def test_each_capability_has_required_fields(self) -> None:
        data = _load_manifest()
        for cap in data.get("capabilities", []):
            for field in ("id", "title", "description"):
                assert field in cap, (
                    f"Capability {cap.get('id', '?')} missing field: {field}"
                )
            assert isinstance(cap["id"], str)
            assert len(cap["id"]) > 0
            assert isinstance(cap["title"], str)
            assert len(cap["title"]) > 0
            assert isinstance(cap["description"], str)
            assert len(cap["description"]) > 0

    def test_local_recall_capability_exists(self) -> None:
        data = _load_manifest()
        caps = data.get("capabilities", [])
        cap_ids = [c.get("id", "") for c in caps]
        assert "logion.recall.search" in cap_ids, (
            "Manifest must include logion.recall.search capability"
        )

    def test_creator_capability_exists(self) -> None:
        data = _load_manifest()
        caps = data.get("capabilities", [])
        cap_ids = [c.get("id", "") for c in caps]
        assert "logion.course.author" in cap_ids, (
            "Manifest must include logion.course.author capability"
        )
        assert "logion.course.operate" in cap_ids, (
            "Manifest must include logion.course.operate capability"
        )

    def test_safety_requires_confirmation(self) -> None:
        data = _load_manifest()
        safety = data.get("safety", {})
        confirmation = safety.get("requires_confirmation", [])
        assert isinstance(confirmation, list), (
            "safety.requires_confirmation must be a list"
        )
        for action in REQUIRED_CONFIRMATION_ACTIONS:
            assert action in confirmation, (
                f"safety.requires_confirmation missing action: {action}"
            )

    def test_required_tools(self) -> None:
        data = _load_manifest()
        tools = data.get("required_tools", [])
        assert isinstance(tools, list), "required_tools must be a list"
        assert "terminal" in tools, "terminal must be in required_tools"
        assert "file" in tools, "file must be in required_tools"

    def test_required_env_is_empty(self) -> None:
        data = _load_manifest()
        env = data.get("required_env", [])
        assert isinstance(env, list), "required_env must be a list"
        assert len(env) == 0, (
            "Manifest must not require environment variables by default"
        )
