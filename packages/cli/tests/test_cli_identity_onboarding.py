# SPDX-License-Identifier: MIT
"""Tests for ``logion identity onboarding``."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from cli._json import JsonObject
from cli.main import main

MATCHER = "Bash(logion courses report-usage:*)"


class FakeIdentityResource:
    def __init__(self) -> None:
        self.calls: list[tuple[str, JsonObject]] = []

    def create_user_with_agent(self, **kwargs: object) -> JsonObject:
        self.calls.append(("create_user_with_agent", kwargs))
        return {
            "user": {"id": "u1", "email": kwargs["email"]},
            "agent": {"id": "a1", "name": kwargs["agent_name"]},
            "api_key": {"key": "lg-abc123", "prefix": "lg-abc"},
            "api_key_prefix": "lg-abc",  # pragma: allowlist secret
        }

    def rotate_api_key(self, **kwargs: object) -> JsonObject:
        self.calls.append(("rotate_api_key", kwargs))
        return {
            "api_key": {"key": "lg-repaired", "prefix": "lg-rep"},
            "api_key_prefix": "lg-rep",  # pragma: allowlist secret
        }


class FakeClient:
    def __init__(self, identity: FakeIdentityResource) -> None:
        self.v1 = SimpleNamespace(identity=identity)

    def close(self) -> None:
        pass


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> SimpleNamespace:
    home = tmp_path / "home"
    proj = tmp_path / "proj"
    logion_home = tmp_path / "logion"
    for d in (home, proj, logion_home):
        d.mkdir()
    monkeypatch.setenv("LOGION_HOME", str(logion_home))
    monkeypatch.setattr(Path, "home", classmethod(lambda _cls: home))
    monkeypatch.chdir(proj)
    monkeypatch.delenv("LOGION_PASSWORD", raising=False)
    # A stray companion-source from a dev-rig shell must not leak in.
    monkeypatch.delenv("LOGION_COMPANION_BUNDLE_SOURCE", raising=False)
    identity = FakeIdentityResource()
    monkeypatch.setattr(
        "cli._context.LogionClient",
        lambda **_: FakeClient(identity),
    )
    return SimpleNamespace(
        home=home, proj=proj, logion_home=logion_home, identity=identity
    )


def _stdout_data(capsys: pytest.CaptureFixture[str]) -> JsonObject:
    return json.loads(capsys.readouterr().out)["data"]


def test_onboarding_provisions_identity(
    env: SimpleNamespace, capsys: pytest.CaptureFixture[str]
) -> None:
    code = main([
        "identity",
        "onboarding",
        "--email",
        "u@example.com",
        "--agent-name",
        "Worker",
        "--password",
        "testpass1",
        "--no-enable-autopost",
        "--json",
    ])
    assert code == 0
    creds = json.loads((env.logion_home / "credentials.json").read_text())
    assert creds["user_id"] == "u1"
    assert creds["agent_id"] == "a1"
    assert creds["email"] == "u@example.com"
    assert creds["api_key"] == "lg-abc123"
    assert creds["api_key_prefix"] == "lg-abc"
    data = _stdout_data(capsys)
    assert data["created"] is True
    assert data["autopost"] == {"enabled": False}


def test_onboarding_reuses_existing_identity(
    env: SimpleNamespace, capsys: pytest.CaptureFixture[str]
) -> None:
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "existing-user"})
    )
    code = main([
        "identity",
        "onboarding",
        "--no-enable-autopost",
        "--json",
    ])
    assert code == 0
    data = _stdout_data(capsys)
    assert data["created"] is False
    assert data["user_id"] == "existing-user"
    # No provisioning call.
    assert env.identity.calls == []


def test_onboarding_repairs_missing_stored_api_key(
    env: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (env.logion_home / "credentials.json").write_text(
        json.dumps({
            "schema_version": 1,
            "user_id": "existing-user",
            "agent_id": "existing-agent",
        })
    )

    code = main([
        "identity",
        "onboarding",
        "--password",
        "testpass1",
        "--no-enable-autopost",
        "--no-companion",
        "--json",
    ])

    assert code == 0
    assert env.identity.calls == [
        (
            "rotate_api_key",
            {
                "user_id": "existing-user",
                "agent_id": "existing-agent",
                "user_password": "testpass1",
            },
        )
    ]
    creds = json.loads((env.logion_home / "credentials.json").read_text())
    assert creds["api_key"] == "lg-repaired"
    assert creds["api_key_prefix"] == "lg-rep"
    data = _stdout_data(capsys)
    assert data["credentials"]["api_key_persisted"] is True


def test_onboarding_enables_autopost_project_scope(
    env: SimpleNamespace, capsys: pytest.CaptureFixture[str]
) -> None:
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    code = main([
        "identity",
        "onboarding",
        "--enable-autopost",
        "--harness",
        "claude-code",
        "--autopost-scope",
        "project",
        "--json",
    ])
    assert code == 0
    settings = json.loads((env.proj / ".claude" / "settings.json").read_text())
    assert settings["permissions"]["allow"] == [MATCHER]
    data = _stdout_data(capsys)
    assert data["autopost"]["enabled"] is True
    assert data["autopost"]["scope"] == "project"
    assert data["autopost"]["harnesses"][0]["changed"] is True


def test_onboarding_autopost_global_scope(env: SimpleNamespace) -> None:
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    code = main([
        "identity",
        "onboarding",
        "--enable-autopost",
        "--harness",
        "claude-code",
        "--autopost-scope",
        "global",
    ])
    assert code == 0
    settings = json.loads((env.home / ".claude" / "settings.json").read_text())
    assert settings["permissions"]["allow"] == [MATCHER]


def test_onboarding_unknown_harness_errors(
    env: SimpleNamespace, capsys: pytest.CaptureFixture[str]
) -> None:
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    code = main([
        "identity",
        "onboarding",
        "--enable-autopost",
        "--harness",
        "bogus",
    ])
    assert code == 2
    assert "unknown harness" in capsys.readouterr().err


def test_onboarding_unknown_harness_with_no_autopost_errors(
    env: SimpleNamespace, capsys: pytest.CaptureFixture[str]
) -> None:
    """An explicit but unknown --harness is a hard error even when
    autopost is disabled, so the companion step never silently skips."""
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    code = main([
        "identity",
        "onboarding",
        "--no-enable-autopost",
        "--harness",
        "bogus",
        "--no-companion",
    ])
    assert code == 2
    assert "unknown harness" in capsys.readouterr().err


def test_ensure_symlink_replaces_existing_symlink_with_real_copy(
    tmp_path: Path,
) -> None:
    """Harness installs must be real copies, not symlinks."""
    from cli._harness.custom import CustomPathHarness
    from cli.commands.identity._companion import COMPANION_COURSE_ID
    from cli.commands.identity._onboarding_helpers import ensure_symlink

    skill_dir = tmp_path / "skills"
    old_source = tmp_path / "old"
    old_source.mkdir()
    skill_dir.mkdir()
    (skill_dir / COMPANION_COURSE_ID).symlink_to(
        old_source,
        target_is_directory=True,
    )
    install_dest = tmp_path / "installed"
    install_dest.mkdir()
    (install_dest / "SKILL.md").write_text("---\nname: logion\n---\n")

    ensure_symlink(CustomPathHarness(skill_dir), install_dest)

    copied = skill_dir / COMPANION_COURSE_ID
    assert copied.is_dir()
    assert not copied.is_symlink()
    assert (copied / "SKILL.md").is_file()


def test_onboarding_unknown_harness_with_agent_dir_still_errors(
    env: SimpleNamespace,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An unknown --harness is a hard error even with --agent-dir set.

    --agent-dir only overrides the companion target; --harness still
    drives the autopost grant, so an unknown value must not slip through
    to _autopost.apply (which would exit 2 with no clear message).
    """
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    code = main([
        "identity",
        "onboarding",
        "--enable-autopost",
        "--harness",
        "bogus",
        "--agent-dir",
        str(tmp_path / "custom"),
    ])
    assert code == 2
    assert "unknown harness" in capsys.readouterr().err


@pytest.mark.usefixtures("env")
def test_onboarding_noninteractive_missing_email_errors(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    code = main([
        "identity",
        "onboarding",
        "--agent-name",
        "Worker",
        "--password",
        "testpass1",
        "--no-enable-autopost",
    ])
    assert code == 2
    assert "--email is required" in capsys.readouterr().err


def test_onboarding_autodetect_no_harness_is_noted(
    env: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    monkeypatch.setattr(
        "cli.commands.identity._harness_select.detect_present", list
    )
    code = main([
        "identity",
        "onboarding",
        "--enable-autopost",
        "--json",
    ])
    assert code == 0
    data = _stdout_data(capsys)
    assert data["autopost"]["enabled"] is True
    assert data["autopost"]["harnesses"] == []


def test_onboarding_prompt_enables_autopost(
    env: SimpleNamespace, monkeypatch: pytest.MonkeyPatch
) -> None:
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt="": "y")
    code = main([
        "identity",
        "onboarding",
        "--harness",
        "claude-code",
    ])
    assert code == 0
    settings = json.loads((env.home / ".claude" / "settings.json").read_text())
    assert MATCHER in settings["permissions"]["allow"]


# ---------------------------------------------------------------------------
# Companion + consent tests
# ---------------------------------------------------------------------------


def _make_bundle(tmp_path: Path) -> Path:
    """Create a minimal companion bundle dir with a valid bundle layout."""
    bundle = tmp_path / "bundle"
    (bundle / "course").mkdir(parents=True)
    bundle.mkdir(exist_ok=True)
    (bundle / "SKILL.md").write_text(
        "---\nname: logion\n"
        "version: 0.1.0\n"
        "description: First-party companion.\n"
        "license: MIT\n"
        "---\n# Companion\n"
    )
    (bundle / "LICENSE").write_text("MIT test license\n", encoding="utf-8")
    (bundle / "course" / "capabilities.yaml").write_text(
        "version: 1\nsummary: companion\ntools:\n  - terminal\n  - file\n",
        encoding="utf-8",
    )
    return bundle


def _make_tarball(tmp_path: Path) -> Path:
    """Build a companion tarball with the real top-level prefix dir.

    Mirrors ``package_skill.py``: files live under
    ``logion-marketplace-companion-<version>/`` inside the archive.
    """
    import tarfile

    bundle = _make_bundle(tmp_path)
    tarball = tmp_path / "logion-marketplace-companion-0.1.0.tar.gz"
    with tarfile.open(tarball, "w:gz") as tf:
        tf.add(bundle, arcname="logion-marketplace-companion-0.1.0")
    return tarball


def test_onboarding_companion_from_tarball(
    env: SimpleNamespace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tarball = _make_tarball(tmp_path)
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    code = main([
        "identity",
        "onboarding",
        "--no-enable-autopost",
        "--companion-source",
        str(tarball),
        "--harness",
        "claude-code",
        "--json",
    ])
    assert code == 0
    skill_dir = env.home / ".claude" / "skills" / "logion"
    assert skill_dir.is_dir()
    assert not skill_dir.is_symlink()


def test_onboarding_companion_from_dir_holding_tarball(
    env: SimpleNamespace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The dev rig points the source at a dir that holds the tarball.
    tarball = _make_tarball(tmp_path)
    holder = tmp_path / "companion-bundle"
    holder.mkdir()
    tarball.rename(holder / tarball.name)
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    code = main([
        "identity",
        "onboarding",
        "--no-enable-autopost",
        "--companion-source",
        str(holder),
        "--harness",
        "claude-code",
        "--json",
    ])
    assert code == 0
    skill_dir = env.home / ".claude" / "skills" / "logion"
    assert skill_dir.is_dir()
    assert not skill_dir.is_symlink()


def test_onboarding_uses_installer_extracted_companion(
    env: SimpleNamespace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """onboarding finds the companion extracted by curl install."""
    bundle = _make_bundle(tmp_path)
    installed = (
        env.logion_home
        / "installed"
        / "logion-marketplace-companion"
        / "0.1.0"
    )
    installed.mkdir(parents=True)
    for child in bundle.iterdir():
        if child.is_file():
            (installed / child.name).write_bytes(child.read_bytes())
        elif child.is_dir():
            import shutil

            shutil.copytree(child, installed / child.name)
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    code = main([
        "identity",
        "onboarding",
        "--no-enable-autopost",
        "--harness",
        "claude-code",
        "--json",
    ])

    assert code == 0
    skill_dir = env.home / ".claude" / "skills" / "logion"
    assert skill_dir.is_dir()
    assert not skill_dir.is_symlink()


def test_onboarding_interactive_selects_subset(
    env: SimpleNamespace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cli._harness import get_adapter

    bundle = _make_bundle(tmp_path)
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: "1")
    monkeypatch.setattr(
        "cli.commands.identity._harness_select.detect_present",
        lambda: [get_adapter("claude-code"), get_adapter("codex")],
    )
    code = main([
        "identity",
        "onboarding",
        "--enable-autopost",
        "--companion-source",
        str(bundle),
        "--json",
    ])
    assert code == 0
    # Only the picked harness (claude-code) is configured.
    settings = json.loads((env.home / ".claude" / "settings.json").read_text())
    assert MATCHER in settings["permissions"]["allow"]
    skill_dir = env.home / ".claude" / "skills" / "logion"
    assert skill_dir.is_dir()
    assert not skill_dir.is_symlink()
    # codex was offered but not picked → untouched.
    assert not (env.home / ".codex" / "config.toml").exists()


def test_onboarding_repeated_harness_targets_multiple(
    env: SimpleNamespace,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _make_bundle(tmp_path)
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    code = main([
        "identity",
        "onboarding",
        "--enable-autopost",
        "--companion-source",
        str(bundle),
        "--harness",
        "claude-code",
        "--harness",
        "codex",
        "--json",
    ])
    assert code == 0
    data = _stdout_data(capsys)
    granted = {h["harness"] for h in data["autopost"]["harnesses"]}
    assert granted == {"claude-code", "codex"}


def test_onboarding_interactive_json_stdout_stays_clean(
    env: SimpleNamespace,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The harness prompt must not leak onto stdout, or --json breaks.
    from cli._harness import get_adapter

    bundle = _make_bundle(tmp_path)
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: "1")
    monkeypatch.setattr(
        "cli.commands.identity._harness_select.detect_present",
        lambda: [get_adapter("claude-code")],
    )
    code = main([
        "identity",
        "onboarding",
        "--enable-autopost",
        "--companion-source",
        str(bundle),
        "--json",
    ])
    assert code == 0
    # _stdout_data json.loads(stdout): raises if the prompt leaked there.
    data = _stdout_data(capsys)
    assert data["user_id"] == "u1"


def test_onboarding_no_steps_skips_harness_prompt(
    env: SimpleNamespace,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # No autopost and --no-companion → no step needs a harness, so we
    # must not prompt even in a TTY.
    from cli._harness import get_adapter

    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    def _no_input(*_a: object, **_k: object) -> str:
        raise AssertionError("should not prompt when no step needs a harness")

    monkeypatch.setattr("builtins.input", _no_input)
    monkeypatch.setattr(
        "cli.commands.identity._harness_select.detect_present",
        lambda: [get_adapter("claude-code")],
    )
    code = main([
        "identity",
        "onboarding",
        "--no-enable-autopost",
        "--no-companion",
    ])
    assert code == 0


def test_onboarding_invalid_companion_source_is_clear(
    env: SimpleNamespace,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    bogus = tmp_path / "nope.txt"
    bogus.write_text("not a bundle\n")
    code = main([
        "identity",
        "onboarding",
        "--no-enable-autopost",
        "--companion-source",
        str(bogus),
        "--harness",
        "claude-code",
    ])
    assert code == 0
    err = capsys.readouterr().err
    assert "not a bundle directory or a .tar.gz" in err


def test_onboarding_interactive_empty_selection_skips(
    env: SimpleNamespace,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cli._harness import get_adapter

    bundle = _make_bundle(tmp_path)
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_a, **_k: "")
    monkeypatch.setattr(
        "cli.commands.identity._harness_select.detect_present",
        lambda: [get_adapter("claude-code")],
    )
    code = main([
        "identity",
        "onboarding",
        "--enable-autopost",
        "--companion-source",
        str(bundle),
        "--json",
    ])
    assert code == 0
    data = _stdout_data(capsys)
    assert data["autopost"]["harnesses"] == []
    assert not (env.home / ".claude" / "skills" / "logion").exists()


def test_onboarding_installs_companion_into_skill_dir(
    env: SimpleNamespace,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _make_bundle(tmp_path)
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    code = main([
        "identity",
        "onboarding",
        "--no-enable-autopost",
        "--companion-source",
        str(bundle),
        "--harness",
        "claude-code",
        "--json",
    ])
    assert code == 0
    skill_link = env.home / ".claude" / "skills" / "logion"
    assert skill_link.is_dir()
    assert not skill_link.is_symlink()
    data = _stdout_data(capsys)
    assert data["companion"]["installed"] is True


def test_onboarding_companion_idempotent(
    env: SimpleNamespace,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _make_bundle(tmp_path)
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    main([
        "identity",
        "onboarding",
        "--no-enable-autopost",
        "--companion-source",
        str(bundle),
        "--harness",
        "claude-code",
        "--json",
    ])
    capsys.readouterr()  # discard first run output
    main([
        "identity",
        "onboarding",
        "--no-enable-autopost",
        "--companion-source",
        str(bundle),
        "--harness",
        "claude-code",
        "--json",
    ])
    data = _stdout_data(capsys)
    assert data["companion"]["already"] is True
    assert data["companion"]["installed"] is False


def test_onboarding_no_companion_flag_skips(
    env: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    code = main([
        "identity",
        "onboarding",
        "--no-enable-autopost",
        "--no-companion",
        "--json",
    ])
    assert code == 0
    data = _stdout_data(capsys)
    assert data["companion"]["installed"] is False


def test_onboarding_agent_dir_custom_path(
    env: SimpleNamespace,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = _make_bundle(tmp_path)
    custom_dir = tmp_path / "custom-agent"
    custom_dir.mkdir()
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    code = main([
        "identity",
        "onboarding",
        "--no-enable-autopost",
        "--companion-source",
        str(bundle),
        "--agent-dir",
        str(custom_dir),
        "--json",
    ])
    assert code == 0
    skill_link = custom_dir / "logion"
    assert skill_link.is_dir()
    assert not skill_link.is_symlink()


def test_onboarding_persists_autoreview_consent_true(
    env: SimpleNamespace,
) -> None:
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    code = main([
        "identity",
        "onboarding",
        "--enable-autopost",
        "--harness",
        "claude-code",
        "--no-companion",
    ])
    assert code == 0
    creds = json.loads((env.logion_home / "credentials.json").read_text())
    integrations = json.loads(
        (env.logion_home / "integrations.json").read_text()
    )
    assert creds["autoreview_consent"] is True
    assert integrations["claude-code"]["review_mode"] == "auto"


def test_onboarding_persists_autoreview_consent_false(
    env: SimpleNamespace,
) -> None:
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    code = main([
        "identity",
        "onboarding",
        "--no-enable-autopost",
        "--harness",
        "claude-code",
        "--no-companion",
    ])
    assert code == 0
    creds = json.loads((env.logion_home / "credentials.json").read_text())
    integrations = json.loads(
        (env.logion_home / "integrations.json").read_text()
    )
    assert creds["autoreview_consent"] is False
    assert integrations["claude-code"]["review_mode"] == "off"


def test_onboarding_closing_copy_mentions_agent(
    env: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    code = main([
        "identity",
        "onboarding",
        "--no-enable-autopost",
        "--no-companion",
    ])
    assert code == 0
    err = capsys.readouterr().err
    assert "Logion is ready" in err


# ---------------------------------------------------------------------------
# Marketplace-loop onboarding tests
# ---------------------------------------------------------------------------


def test_onboarding_closing_copy_mentions_structured_search(
    env: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closing copy must teach --category/--tag search, not just free-text."""
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    code = main([
        "identity",
        "onboarding",
        "--no-enable-autopost",
        "--no-companion",
    ])
    assert code == 0
    err = capsys.readouterr().err
    assert "--category" in err
    assert "--tag" in err


def test_onboarding_closing_copy_mentions_bounties(
    env: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Closing copy must mention the bounty step in the marketplace loop."""
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    code = main([
        "identity",
        "onboarding",
        "--no-enable-autopost",
        "--no-companion",
    ])
    assert code == 0
    err = capsys.readouterr().err
    assert "bounty" in err.lower()


def test_onboarding_json_includes_next_steps(
    env: SimpleNamespace,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """JSON onboarding output must include stable next_steps array."""
    (env.logion_home / "credentials.json").write_text(
        json.dumps({"schema_version": 1, "user_id": "u1"})
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    code = main([
        "identity",
        "onboarding",
        "--no-enable-autopost",
        "--no-companion",
        "--json",
    ])
    assert code == 0
    data = _stdout_data(capsys)
    assert "next_steps" in data
    steps = data["next_steps"]
    assert isinstance(steps, list)
    # Verify the stable IDs are present.
    ids = [s["id"] for s in steps]
    expected_ids = {
        "search",
        "inspect",
        "acquire_free",
        "acquire_paid",
        "install",
        "review",
        "bounty",
        "docs",
    }
    assert expected_ids <= set(ids), (
        f"missing next_step IDs: {expected_ids - set(ids)}"
    )


def test_onboarding_examples_do_not_include_yes_for_paid_or_fund() -> None:
    """Paid/funding examples in closing copy must not include --yes.

    Agents must ask for approval; --yes skips the prompt and is only
    for already-confirmed non-interactive execution.
    """
    from cli.commands.identity._closing_copy import (
        CLOSING_COPY,
        ONBOARDING_NEXT_STEPS,
    )

    # Closing copy should not contain --yes.
    assert "--yes" not in CLOSING_COPY, (
        "Closing copy must not include --yes — agents must ask for approval"
    )
    # Next steps JSON should not contain --yes.
    for step in ONBOARDING_NEXT_STEPS:
        assert "--yes" not in step["command"], (
            f"next_step '{step['id']}' must not include --yes"
        )
