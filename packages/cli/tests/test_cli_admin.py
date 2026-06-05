# SPDX-License-Identifier: MIT
"""Tests for the admin commands."""

from __future__ import annotations

from typing import Any

import pytest

from cli.main import main


class FakeAdminResource:
    """Fake admin resource."""

    def __init__(self) -> None:
        self.last_call: tuple[str, dict[str, Any]] = ("", {})

    def list_courses(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("list_courses", kwargs)
        return {"items": [], "next_cursor": None}

    def get_course(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("get_course", kwargs)
        return {"id": kwargs["course_id"], "status": "active"}

    def update_course_status(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("update_course_status", kwargs)
        return {"id": kwargs["course_id"], "status": "blocked"}

    def get_user(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("get_user", kwargs)
        return {"id": kwargs["user_id"], "email": "test@example.com"}

    def suspend_user(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("suspend_user", kwargs)
        return {"id": kwargs["user_id"], "status": "suspended"}

    def unsuspend_user(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("unsuspend_user", kwargs)
        return {"id": kwargs["user_id"], "status": "active"}

    def get_agent(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("get_agent", kwargs)
        return {"id": kwargs["agent_id"], "status": "active"}

    def suspend_agent(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("suspend_agent", kwargs)
        return {"id": kwargs["agent_id"], "status": "suspended"}

    def unsuspend_agent(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("unsuspend_agent", kwargs)
        return {"id": kwargs["agent_id"], "status": "active"}

    def list_reports(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("list_reports", kwargs)
        return {"items": [], "next_cursor": None}

    def get_report(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("get_report", kwargs)
        return {"id": kwargs["report_id"], "status": "open"}

    def resolve_report(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("resolve_report", kwargs)
        return {"id": kwargs["report_id"], "status": "resolved"}

    def dismiss_report(self, **kwargs: Any) -> dict[str, Any]:
        self.last_call = ("dismiss_report", kwargs)
        return {"id": kwargs["report_id"], "status": "dismissed"}


class FakeV1Namespace:
    def __init__(self, admin: FakeAdminResource) -> None:
        self.admin = admin


class FakeClient:
    def __init__(self, v1: FakeV1Namespace) -> None:
        self.v1 = v1

    def close(self) -> None:
        pass


def _patch_client(monkeypatch: pytest.MonkeyPatch, fake: FakeClient) -> None:
    monkeypatch.setattr("cli._context.LogionClient", lambda **_: fake)


# ── Visibility gating ─────────────────────────────────────────────


def test_admin_hidden_by_default() -> None:
    """Without LOGION_ENABLE_ADMIN, admin subcommand exits with code 2."""
    code = main(["admin"])
    assert code == 2


def test_admin_visible_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """With LOGION_ENABLE_ADMIN=1, 'users' appears in admin help."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    with pytest.raises(SystemExit) as exc_info:
        main(["admin", "--help"])
    assert exc_info.value.code == 0
    output = capsys.readouterr().out
    assert "users" in output


# ── Courses ─────────────────────────────────────────────────────────


def test_admin_courses_list_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin courses list forwards args to SDK."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    admin = FakeAdminResource()
    fake = FakeClient(v1=FakeV1Namespace(admin=admin))
    _patch_client(monkeypatch, fake)
    code = main([
        "admin",
        "courses",
        "list",
        "--status",
        "active",
        "--limit",
        "10",
        "--json",
    ])
    assert code == 0
    method, kwargs = admin.last_call
    assert method == "list_courses"
    assert kwargs["status"] == "active"
    assert kwargs["limit"] == 10


def test_admin_courses_get_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin courses get forwards course_id."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    admin = FakeAdminResource()
    fake = FakeClient(v1=FakeV1Namespace(admin=admin))
    _patch_client(monkeypatch, fake)
    code = main([
        "admin",
        "courses",
        "get",
        "550e8400-e29b-41d4-a716-446655440000",
        "--json",
    ])
    assert code == 0
    method, kwargs = admin.last_call
    assert method == "get_course"
    assert kwargs["course_id"] == "550e8400-e29b-41d4-a716-446655440000"


def test_admin_courses_block_requires_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin courses block rejects without --yes."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    code = main([
        "admin",
        "courses",
        "block",
        "550e8400-e29b-41d4-a716-446655440000",
        "--json",
    ])
    assert code == 2


def test_admin_courses_block_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin courses block calls SDK with --yes."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    admin = FakeAdminResource()
    fake = FakeClient(v1=FakeV1Namespace(admin=admin))
    _patch_client(monkeypatch, fake)
    code = main([
        "admin",
        "courses",
        "block",
        "550e8400-e29b-41d4-a716-446655440000",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = admin.last_call
    assert method == "update_course_status"
    assert kwargs["course_id"] == "550e8400-e29b-41d4-a716-446655440000"


def test_admin_courses_get_invalid_uuid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin courses get rejects an invalid UUID."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    code = main([
        "admin",
        "courses",
        "get",
        "not-a-uuid",
        "--json",
    ])
    assert code == 2


# ── Users ────────────────────────────────────────────────────────────


def test_admin_users_get_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin users get forwards user_id."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    admin = FakeAdminResource()
    fake = FakeClient(v1=FakeV1Namespace(admin=admin))
    _patch_client(monkeypatch, fake)
    code = main([
        "admin",
        "users",
        "get",
        "550e8400-e29b-41d4-a716-446655440000",
        "--json",
    ])
    assert code == 0
    method, kwargs = admin.last_call
    assert method == "get_user"
    assert kwargs["user_id"] == "550e8400-e29b-41d4-a716-446655440000"


def test_admin_users_suspend_requires_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin users suspend rejects without --yes."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    code = main([
        "admin",
        "users",
        "suspend",
        "550e8400-e29b-41d4-a716-446655440000",
        "--json",
    ])
    assert code == 2


def test_admin_users_suspend_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin users suspend calls SDK with --yes."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    admin = FakeAdminResource()
    fake = FakeClient(v1=FakeV1Namespace(admin=admin))
    _patch_client(monkeypatch, fake)
    code = main([
        "admin",
        "users",
        "suspend",
        "550e8400-e29b-41d4-a716-446655440000",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = admin.last_call
    assert method == "suspend_user"
    assert kwargs["user_id"] == "550e8400-e29b-41d4-a716-446655440000"


def test_admin_users_unsuspend_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin users unsuspend calls SDK with --yes."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    admin = FakeAdminResource()
    fake = FakeClient(v1=FakeV1Namespace(admin=admin))
    _patch_client(monkeypatch, fake)
    code = main([
        "admin",
        "users",
        "unsuspend",
        "550e8400-e29b-41d4-a716-446655440000",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = admin.last_call
    assert method == "unsuspend_user"
    assert kwargs["user_id"] == "550e8400-e29b-41d4-a716-446655440000"


# ── Agents ──────────────────────────────────────────────────────────


def test_admin_agents_get_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin agents get forwards agent_id."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    admin = FakeAdminResource()
    fake = FakeClient(v1=FakeV1Namespace(admin=admin))
    _patch_client(monkeypatch, fake)
    code = main([
        "admin",
        "agents",
        "get",
        "550e8400-e29b-41d4-a716-446655440000",
        "--json",
    ])
    assert code == 0
    method, kwargs = admin.last_call
    assert method == "get_agent"
    assert kwargs["agent_id"] == "550e8400-e29b-41d4-a716-446655440000"


def test_admin_agents_suspend_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin agents suspend calls SDK with --yes."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    admin = FakeAdminResource()
    fake = FakeClient(v1=FakeV1Namespace(admin=admin))
    _patch_client(monkeypatch, fake)
    code = main([
        "admin",
        "agents",
        "suspend",
        "550e8400-e29b-41d4-a716-446655440000",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = admin.last_call
    assert method == "suspend_agent"
    assert kwargs["agent_id"] == "550e8400-e29b-41d4-a716-446655440000"


def test_admin_agents_unsuspend_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin agents unsuspend calls SDK with --yes."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    admin = FakeAdminResource()
    fake = FakeClient(v1=FakeV1Namespace(admin=admin))
    _patch_client(monkeypatch, fake)
    code = main([
        "admin",
        "agents",
        "unsuspend",
        "550e8400-e29b-41d4-a716-446655440000",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = admin.last_call
    assert method == "unsuspend_agent"
    assert kwargs["agent_id"] == "550e8400-e29b-41d4-a716-446655440000"


# ── Reports ─────────────────────────────────────────────────────────


def test_admin_reports_list_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin reports list forwards args to SDK."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    admin = FakeAdminResource()
    fake = FakeClient(v1=FakeV1Namespace(admin=admin))
    _patch_client(monkeypatch, fake)
    code = main([
        "admin",
        "reports",
        "list",
        "--status",
        "open",
        "--limit",
        "10",
        "--json",
    ])
    assert code == 0
    method, kwargs = admin.last_call
    assert method == "list_reports"
    assert kwargs["status"] == "open"
    assert kwargs["limit"] == 10


def test_admin_reports_get_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin reports get forwards report_id."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    admin = FakeAdminResource()
    fake = FakeClient(v1=FakeV1Namespace(admin=admin))
    _patch_client(monkeypatch, fake)
    code = main([
        "admin",
        "reports",
        "get",
        "550e8400-e29b-41d4-a716-446655440000",
        "--json",
    ])
    assert code == 0
    method, kwargs = admin.last_call
    assert method == "get_report"
    assert kwargs["report_id"] == "550e8400-e29b-41d4-a716-446655440000"


def test_admin_reports_resolve_requires_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin reports resolve rejects without --yes."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    code = main([
        "admin",
        "reports",
        "resolve",
        "550e8400-e29b-41d4-a716-446655440000",
        "--json",
    ])
    assert code == 2


def test_admin_reports_resolve_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin reports resolve calls SDK with --yes."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    admin = FakeAdminResource()
    fake = FakeClient(v1=FakeV1Namespace(admin=admin))
    _patch_client(monkeypatch, fake)
    code = main([
        "admin",
        "reports",
        "resolve",
        "550e8400-e29b-41d4-a716-446655440000",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = admin.last_call
    assert method == "resolve_report"
    assert kwargs["report_id"] == "550e8400-e29b-41d4-a716-446655440000"


def test_admin_reports_resolve_with_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin reports resolve forwards --note to SDK."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    admin = FakeAdminResource()
    fake = FakeClient(v1=FakeV1Namespace(admin=admin))
    _patch_client(monkeypatch, fake)
    code = main([
        "admin",
        "reports",
        "resolve",
        "550e8400-e29b-41d4-a716-446655440000",
        "--note",
        "Resolved as duplicate",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = admin.last_call
    assert method == "resolve_report"
    assert kwargs["report_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert kwargs["note"] == "Resolved as duplicate"


def test_admin_reports_dismiss_requires_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin reports dismiss rejects without --yes."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    code = main([
        "admin",
        "reports",
        "dismiss",
        "550e8400-e29b-41d4-a716-446655440000",
        "--reason",
        "spam",
        "--json",
    ])
    assert code == 2


def test_admin_reports_dismiss_calls_client(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin reports dismiss calls SDK with --yes and --reason."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    admin = FakeAdminResource()
    fake = FakeClient(v1=FakeV1Namespace(admin=admin))
    _patch_client(monkeypatch, fake)
    code = main([
        "admin",
        "reports",
        "dismiss",
        "550e8400-e29b-41d4-a716-446655440000",
        "--reason",
        "spam",
        "--yes",
        "--json",
    ])
    assert code == 0
    method, kwargs = admin.last_call
    assert method == "dismiss_report"
    assert kwargs["report_id"] == "550e8400-e29b-41d4-a716-446655440000"
    assert kwargs["reason"] == "spam"


# ── UUID validation ────────────────────────────────────────────────


def test_admin_users_get_invalid_uuid(monkeypatch: pytest.MonkeyPatch) -> None:
    """admin users get rejects an invalid UUID."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    code = main([
        "admin",
        "users",
        "get",
        "not-a-uuid",
        "--json",
    ])
    assert code == 2


def test_admin_agents_get_invalid_uuid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin agents get rejects an invalid UUID."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    code = main([
        "admin",
        "agents",
        "get",
        "not-a-uuid",
        "--json",
    ])
    assert code == 2


def test_admin_reports_get_invalid_uuid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin reports get rejects an invalid UUID."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    code = main([
        "admin",
        "reports",
        "get",
        "not-a-uuid",
        "--json",
    ])
    assert code == 2


# ── Mutation commands require --yes ─────────────────────────────────


def test_admin_users_unsuspend_requires_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin users unsuspend rejects without --yes."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    code = main([
        "admin",
        "users",
        "unsuspend",
        "550e8400-e29b-41d4-a716-446655440000",
        "--json",
    ])
    assert code == 2


def test_admin_agents_suspend_requires_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin agents suspend rejects without --yes."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    code = main([
        "admin",
        "agents",
        "suspend",
        "550e8400-e29b-41d4-a716-446655440000",
        "--json",
    ])
    assert code == 2


def test_admin_agents_unsuspend_requires_yes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """admin agents unsuspend rejects without --yes."""
    monkeypatch.setenv("LOGION_ENABLE_ADMIN", "1")
    code = main([
        "admin",
        "agents",
        "unsuspend",
        "550e8400-e29b-41d4-a716-446655440000",
        "--json",
    ])
    assert code == 2
