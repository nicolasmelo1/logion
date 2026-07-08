"""Tests for the CLI."""

from __future__ import annotations

import pytest

from social_management.cli import main


def test_x_post_dry_run_prints_cost_exit_0(
    env,
    capsys,
    monkeypatch,
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    env(
        X_BACKEND="api",
        X_API_KEY="k",
        X_API_SECRET="s",
        X_ACCESS_TOKEN="t",
        X_ACCESS_SECRET="ts",  # pragma: allowlist secret
        X_MONTHLY_BUDGET_CENTS="1000",
    )
    monkeypatch.chdir(tmp_path)
    # Avoid loading a real .env.local
    from social_management.core import config as cfg_module

    original_from_env = cfg_module.SocialConfig.from_env

    def patched_from_env(
        *,
        env_local=None,  # type: ignore[no-untyped-def]
    ):
        return original_from_env(env_local=tmp_path / "nonexistent.env")

    monkeypatch.setattr(cfg_module.SocialConfig, "from_env", patched_from_env)
    code = main(["x", "post", "--text", "hi", "--dry-run"])
    assert code == 0
    captured = capsys.readouterr()
    assert "$0.02" in captured.out


def test_x_post_no_confirm_exit_1(
    env,
    capsys,
    monkeypatch,
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    env(
        X_BACKEND="api",
        X_API_KEY="k",
        X_API_SECRET="s",
        X_ACCESS_TOKEN="t",
        X_ACCESS_SECRET="ts",  # pragma: allowlist secret
        X_MONTHLY_BUDGET_CENTS="1000",
    )
    monkeypatch.chdir(tmp_path)
    from social_management.core import config as cfg_module

    original_from_env = cfg_module.SocialConfig.from_env

    def patched_from_env(
        *,
        env_local=None,  # type: ignore[no-untyped-def]
    ):
        return original_from_env(env_local=tmp_path / "nonexistent.env")

    monkeypatch.setattr(cfg_module.SocialConfig, "from_env", patched_from_env)
    code = main(["x", "post", "--text", "hi"])
    assert code == 1
    captured = capsys.readouterr()
    assert "--confirm" in captured.err


def test_x_post_from_file_preserves_newlines(
    env,
    capsys,
    monkeypatch,
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    env(
        X_BACKEND="api",
        X_API_KEY="k",
        X_API_SECRET="s",
        X_ACCESS_TOKEN="t",
        X_ACCESS_SECRET="ts",  # pragma: allowlist secret
        X_MONTHLY_BUDGET_CENTS="1000",
    )
    monkeypatch.chdir(tmp_path)
    from social_management.core import config as cfg_module

    original_from_env = cfg_module.SocialConfig.from_env

    def patched_from_env(
        *,
        env_local=None,  # type: ignore[no-untyped-def]
    ):
        return original_from_env(env_local=tmp_path / "nonexistent.env")

    monkeypatch.setattr(cfg_module.SocialConfig, "from_env", patched_from_env)
    post_file = tmp_path / "post.txt"
    post_file.write_text("line one\nline two\nline three")
    code = main([
        "x",
        "post",
        "--file",
        str(post_file),
        "--dry-run",
    ])
    assert code == 0
    captured = capsys.readouterr()
    assert "line one\nline two\nline three" in captured.out


def test_x_post_requires_text_or_file(
    env,
    capsys,
    monkeypatch,
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    env(
        X_BACKEND="api",
        X_API_KEY="k",
        X_API_SECRET="s",
        X_ACCESS_TOKEN="t",
        X_ACCESS_SECRET="ts",  # pragma: allowlist secret
        X_MONTHLY_BUDGET_CENTS="1000",
    )
    monkeypatch.chdir(tmp_path)
    from social_management.core import config as cfg_module

    original_from_env = cfg_module.SocialConfig.from_env

    def patched_from_env(
        *,
        env_local=None,  # type: ignore[no-untyped-def]
    ):
        return original_from_env(env_local=tmp_path / "nonexistent.env")

    monkeypatch.setattr(cfg_module.SocialConfig, "from_env", patched_from_env)
    code = main(["x", "post", "--dry-run"])
    assert code == 2
    captured = capsys.readouterr()
    assert "--text or --file required" in captured.err


def test_discord_post_dry_run_exit_0(
    env,
    capsys,
    monkeypatch,
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    env(DISCORD_WEBHOOK_GENERAL="https://discord.com/api/webhooks/abc")
    monkeypatch.chdir(tmp_path)
    from social_management.core import config as cfg_module

    original_from_env = cfg_module.SocialConfig.from_env

    def patched_from_env(
        *,
        env_local=None,  # type: ignore[no-untyped-def]
    ):
        return original_from_env(env_local=tmp_path / "nonexistent.env")

    monkeypatch.setattr(cfg_module.SocialConfig, "from_env", patched_from_env)
    code = main([
        "discord",
        "post",
        "--channel",
        "general",
        "--text",
        "hi",
        "--dry-run",
    ])
    assert code == 0
    captured = capsys.readouterr()
    assert "hi" in captured.out


def test_discord_post_from_file_preserves_newlines(
    env,
    capsys,
    monkeypatch,
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    env(DISCORD_WEBHOOK_GENERAL="https://discord.com/api/webhooks/abc")
    monkeypatch.chdir(tmp_path)
    from social_management.core import config as cfg_module

    original_from_env = cfg_module.SocialConfig.from_env

    def patched_from_env(
        *,
        env_local=None,  # type: ignore[no-untyped-def]
    ):
        return original_from_env(env_local=tmp_path / "nonexistent.env")

    monkeypatch.setattr(cfg_module.SocialConfig, "from_env", patched_from_env)
    post_file = tmp_path / "post.txt"
    post_file.write_text("line one\nline two\nline three")
    code = main([
        "discord",
        "post",
        "--channel",
        "general",
        "--file",
        str(post_file),
        "--dry-run",
    ])
    assert code == 0
    captured = capsys.readouterr()
    assert "line one\nline two\nline three" in captured.out


def test_discord_post_requires_text_or_file(
    env,
    capsys,
    monkeypatch,
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    env(DISCORD_WEBHOOK_GENERAL="https://discord.com/api/webhooks/abc")
    monkeypatch.chdir(tmp_path)
    from social_management.core import config as cfg_module

    original_from_env = cfg_module.SocialConfig.from_env

    def patched_from_env(
        *,
        env_local=None,  # type: ignore[no-untyped-def]
    ):
        return original_from_env(env_local=tmp_path / "nonexistent.env")

    monkeypatch.setattr(cfg_module.SocialConfig, "from_env", patched_from_env)
    code = main(["discord", "post", "--channel", "general", "--dry-run"])
    assert code == 2
    captured = capsys.readouterr()
    assert "--text or --file required" in captured.err


def test_queue_add_then_list(
    env,
    capsys,
    monkeypatch,
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    env()
    monkeypatch.chdir(tmp_path)
    from social_management.content import constants as content_constants
    from social_management.core import config as cfg_module

    original_from_env = cfg_module.SocialConfig.from_env

    def patched_from_env(
        *,
        env_local=None,  # type: ignore[no-untyped-def]
    ):
        return original_from_env(env_local=tmp_path / "nonexistent.env")

    monkeypatch.setattr(cfg_module.SocialConfig, "from_env", patched_from_env)
    # Make content queue use tmp_path/content.
    monkeypatch.setattr(content_constants, "CONTENT_DIR", tmp_path / "content")
    code = main([
        "queue",
        "add",
        "--platform",
        "x",
        "--target",
        "x",
        "--text",
        "draft message",
    ])
    assert code == 0
    captured = capsys.readouterr()
    assert "queued" in captured.out

    code = main(["queue", "list"])
    assert code == 0
    captured = capsys.readouterr()
    assert "draft message" in captured.out


def test_unknown_command_exit_2(
    env,
    monkeypatch,
    tmp_path,  # type: ignore[no-untyped-def]
) -> None:
    env()
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit) as exc_info:
        main(["bogus-command"])
    assert exc_info.value.code == 2
