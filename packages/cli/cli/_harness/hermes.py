# SPDX-License-Identifier: MIT
"""Hermes Agent harness adapter.

Hermes exposes ``on_skill_lifecycle`` to general plugins. This adapter
installs a small stdlib-only observer plugin and enables it in Hermes' opt-in
allow-list.  The observer emits an event only for a named ``loaded`` skill and
passes a transient candidate directory to ``logion usage observe``; Logion
resolves it against local acquisition receipts before writing its fixed-schema,
path-free spool record.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import yaml

from cli._harness._hermes_observer import _PLUGIN_NAME
from cli._harness.base import (
    GrantResult,
    HarnessAdapter,
    HarnessConfigError,
    ObservationPlan,
)
from cli._harness.scopes import (
    REPO_CURRENT,
    REPO_PARENT,
    REPO_ROOT,
    USER,
    ScopeTarget,
    canonical_scope,
)
from cli._json import JsonObject
from cli._local_state import _atomic_write_text


def _git_root(cwd: Path) -> Path | None:
    """Walk up from *cwd* looking for a ``.git`` dir/file."""
    path = Path(cwd).resolve()
    while True:
        if (path / ".git").exists():
            return path
        if path.parent == path:
            return None
        path = path.parent


class HermesAdapter(HarnessAdapter):
    """Hermes adapter with receipt-backed named-skill lifecycle observation."""

    name = "hermes"
    display_name = "Hermes"

    def __init__(
        self,
        *,
        project_dir: Path | None = None,
        home_dir: Path | None = None,
        cwd: Path | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self._project_dir = project_dir
        self._home_dir = home_dir
        self._cwd = cwd
        self._repo_root = repo_root

    def _home(self) -> Path:
        return self._home_dir if self._home_dir is not None else Path.home()

    def _hermes_home(self) -> Path:
        configured = os.environ.get("HERMES_HOME")
        return (
            Path(configured).expanduser()
            if configured
            else self._home() / ".hermes"
        )

    def _cwd_path(self) -> Path:
        if self._cwd is not None:
            return Path(self._cwd)
        if self._project_dir is not None:
            return Path(self._project_dir)
        return Path.cwd()

    def _repo_root_path(self) -> Path | None:
        return (
            Path(self._repo_root)
            if self._repo_root is not None
            else _git_root(self._cwd_path())
        )

    def scope_targets(self, scope: str) -> list[ScopeTarget]:
        cscope, cwd, repo_root = (
            canonical_scope(scope),
            self._cwd_path(),
            self._repo_root_path(),
        )
        if cscope == USER:
            home = self._hermes_home()
            target = home / "skills"
            return [ScopeTarget(USER, home, target, "hermes", target.exists())]
        if cscope == REPO_ROOT:
            if repo_root is None:
                return []
            target = repo_root / ".agents" / "skills"
            return [
                ScopeTarget(
                    REPO_ROOT, repo_root, target, None, target.exists()
                )
            ]
        if cscope == REPO_CURRENT:
            target = cwd / ".agents" / "skills"
            return [
                ScopeTarget(REPO_CURRENT, cwd, target, None, target.exists())
            ]
        if cscope == REPO_PARENT:
            if (
                repo_root is None
                or cwd.parent == repo_root
                or not self._is_inside(cwd, repo_root)
            ):
                return []
            target = cwd.parent / ".agents" / "skills"
            return [
                ScopeTarget(
                    REPO_PARENT, cwd.parent, target, None, target.exists()
                )
            ]
        return []

    @staticmethod
    def _is_inside(child: Path, root: Path) -> bool:
        try:
            child.resolve().relative_to(root.resolve())
        except ValueError:
            return False
        return True

    def skill_dir(self) -> Path:
        return self.scope_targets(USER)[0].target_path

    def is_present(self) -> bool:
        return (
            self._hermes_home().is_dir() or shutil.which("hermes") is not None
        )

    def config_path(self, scope: str) -> Path:  # noqa: ARG002
        return self._hermes_home() / "config.yaml"

    def is_granted(self, scope: str) -> bool:  # noqa: ARG002
        return False

    def grant(self, scope: str) -> GrantResult:
        return GrantResult(
            self.name,
            canonical_scope(scope),
            self.config_path(scope),
            changed=False,
            already=True,
        )

    def revoke(self, scope: str) -> GrantResult:
        return GrantResult(
            self.name,
            canonical_scope(scope),
            self.config_path(scope),
            changed=False,
            already=True,
        )

    def plugin_dir(self, scope: str) -> Path | None:
        """Hermes observation is user-scoped until config is scope-aware."""
        if canonical_scope(scope) != USER:
            return None
        return self._hermes_home() / "plugins" / _PLUGIN_NAME

    def observation_config_path(self, scope: str) -> Path | None:
        return (
            self.config_path(scope)
            if self.plugin_dir(scope) is not None
            else None
        )

    def _load_settings(self, path: Path) -> tuple[str, JsonObject]:
        before = path.read_text(encoding="utf-8") if path.is_file() else ""
        try:
            parsed = yaml.safe_load(before) if before else {}
        except yaml.YAMLError as exc:
            raise HarnessConfigError(
                f"{path}: invalid YAML — refusing to edit"
            ) from exc
        if parsed is None:
            parsed = {}
        if not isinstance(parsed, dict):
            raise HarnessConfigError(
                f"{path}: config root is not an object — refusing to edit"
            )
        return before, parsed

    @staticmethod
    def _settings_text(settings: JsonObject) -> str:
        return yaml.safe_dump(
            settings,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )

    def _prepared_settings(self, path: Path) -> tuple[str, str, bool]:
        before, settings = self._load_settings(path)
        plugins = settings.setdefault("plugins", {})
        if not isinstance(plugins, dict):
            raise HarnessConfigError(
                f"{path}: plugins is not an object — refusing to edit"
            )
        enabled = plugins.setdefault("enabled", [])
        if not isinstance(enabled, list) or not all(
            isinstance(item, str) for item in enabled
        ):
            raise HarnessConfigError(
                f"{path}: plugins.enabled is not a string list — "
                "refusing to edit"
            )
        disabled = plugins.get("disabled", [])
        if not isinstance(disabled, list) or not all(
            isinstance(item, str) for item in disabled
        ):
            raise HarnessConfigError(
                f"{path}: plugins.disabled is not a string list — "
                "refusing to edit"
            )
        changed = False
        if _PLUGIN_NAME in disabled:
            plugins["disabled"] = [
                item for item in disabled if item != _PLUGIN_NAME
            ]
            changed = True
        if _PLUGIN_NAME not in enabled:
            enabled.append(_PLUGIN_NAME)
            changed = True
        after = self._settings_text(settings)
        return before, after, changed

    def _plugin_files(self, path: Path) -> dict[Path, str]:
        import inspect

        from cli._harness import _hermes_observer

        return {
            path / "plugin.yaml": (
                "name: logion-observer\n"
                "version: 1\n"
                "description: Receipt-backed Logion skill lifecycle "
                "observer.\n"
                "hooks:\n  - on_skill_lifecycle\n"
            ),
            path / "__init__.py": inspect.getsource(_hermes_observer),
        }

    def _plugin_is_current(self, path: Path) -> bool:
        return all(
            target.is_file() and target.read_text(encoding="utf-8") == text
            for target, text in self._plugin_files(path).items()
        )

    def plan_observation(self, scope: str) -> ObservationPlan:
        plugin_dir = self.plugin_dir(scope)
        if plugin_dir is None:
            return self._unsupported(scope)
        config_path = self.config_path(scope)
        before, after, settings_changed = self._prepared_settings(config_path)
        current = self._plugin_is_current(plugin_dir)
        return ObservationPlan(
            harness=self.name,
            scope=canonical_scope(scope),
            supported=True,
            path=config_path,
            already=current and not settings_changed,
            changed=settings_changed or not current,
            before=before,
            after=after,
        )

    def enable_observation(self, scope: str) -> ObservationPlan:
        plan = self.plan_observation(scope)
        if not plan.supported or plan.path is None:
            return plan
        plugin_dir = self.plugin_dir(scope)
        if plugin_dir is None:
            return plan
        if plan.before != plan.after:
            _atomic_write_text(plan.path, plan.after)
        if not self._plugin_is_current(plugin_dir):
            for target, content in self._plugin_files(plugin_dir).items():
                _atomic_write_text(target, content)
        return plan

    def _settings_after_disable(
        self, path: Path, before: str, settings: JsonObject
    ) -> str:
        plugins = settings.get("plugins")
        if plugins is None:
            return before
        if not isinstance(plugins, dict):
            raise HarnessConfigError(
                f"{path}: plugins is not an object — refusing to edit"
            )
        enabled = plugins.get("enabled", [])
        if not isinstance(enabled, list) or not all(
            isinstance(item, str) for item in enabled
        ):
            raise HarnessConfigError(
                f"{path}: plugins.enabled is not a string list — "
                "refusing to edit"
            )
        if _PLUGIN_NAME not in enabled:
            return before
        plugins["enabled"] = [item for item in enabled if item != _PLUGIN_NAME]
        return self._settings_text(settings)

    @staticmethod
    def _is_owned_plugin(path: Path) -> bool:
        manifest = path / "plugin.yaml"
        return (
            manifest.is_file()
            and "name: logion-observer" in manifest.read_text(encoding="utf-8")
        )

    def disable_observation(self, scope: str) -> ObservationPlan:
        plugin_dir = self.plugin_dir(scope)
        if plugin_dir is None:
            return self._unsupported(scope)
        path = self.config_path(scope)
        before, settings = self._load_settings(path)
        after = self._settings_after_disable(path, before, settings)
        plugin_owned = self._is_owned_plugin(plugin_dir)
        changed = before != after or plugin_owned
        if before != after:
            _atomic_write_text(path, after)
        if plugin_owned:
            shutil.rmtree(plugin_dir)
        return ObservationPlan(
            harness=self.name,
            scope=canonical_scope(scope),
            supported=True,
            path=path,
            already=not changed,
            changed=changed,
            before=before,
            after=after,
        )
