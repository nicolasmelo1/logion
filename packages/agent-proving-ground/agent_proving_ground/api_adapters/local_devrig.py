from __future__ import annotations

import json
import os
from pathlib import Path

from agent_proving_ground._json import JsonObject
from agent_proving_ground.api_adapters._env import (
    DevrigEnvError,
    build_devrig_env_for_agent,
    env_file_description,
    parse_export_env_file,
    validate_devrig_env,
)
from agent_proving_ground.api_adapters._http import (
    HealthCheckError,
    health_check_endpoint,
)
from agent_proving_ground.api_adapters._queries import (
    LogionApiQueries,
    RoleKeyStore,
)
from agent_proving_ground.api_adapters.base import ApiAdapter, World


class LocalDevrigAdapter(ApiAdapter):
    """Attach-only adapter for the existing public ``logion/`` dev rig.

    This adapter does not start Docker, Postgres, MinIO, the API, or a
    second devrig. It expects ``make dev-up MODE=mock|prod ROLE=...`` to
    have already produced ``.devrig/devrig.env`` in the public repo root.
    It validates that env, health-checks the configured API/mock endpoint,
    and materializes per-agent environments by overriding
    ``LOGION_DEVRIG_ROLE``.
    """

    name = "local-devrig"

    def __init__(
        self,
        *,
        devrig_root: Path | str | None = None,
        api_log_path: Path | str | None = None,
    ) -> None:
        self._root = _resolve_devrig_root(devrig_root)
        self._env_path = self._root / ".devrig" / "devrig.env"
        self._api_log_path = _resolve_api_log_path(self._root, api_log_path)
        self._base_env: dict[str, str] = {}
        self._queries: LogionApiQueries | None = None

    async def start(self) -> None:
        self._base_env = parse_export_env_file(self._env_path)
        self._base_env.setdefault("LOGION_PUBLIC_REPO_PATH", str(self._root))
        validate_devrig_env(self._base_env, label=str(self._env_path))
        await health_check_endpoint(self._base_env["LOGION_API_BASE_URL"])
        role_keys = _role_key_store_from_devrig(self._base_env, [], {})
        self._queries = LogionApiQueries(
            self._base_env["LOGION_API_BASE_URL"], role_keys
        )

    async def create_world(
        self,
        run_id: str,
        scenario_name: str,  # noqa: ARG002
        agent_ids: list[str],
        agent_roles: dict[str, str] | None = None,
    ) -> World:
        if not self._base_env:
            self._base_env = parse_export_env_file(self._env_path)
            self._base_env.setdefault(
                "LOGION_PUBLIC_REPO_PATH", str(self._root)
            )
            validate_devrig_env(self._base_env, label=str(self._env_path))

        role_keys = _role_key_store_from_devrig(
            self._base_env, agent_ids, agent_roles or {}
        )
        agent_env: dict[str, dict[str, str]] = {}
        for agent_id in agent_ids:
            role = (agent_roles or {}).get(agent_id)
            env = build_devrig_env_for_agent(
                self._base_env, agent_id, role, run_id
            )
            resolved_role = env.get("LOGION_DEVRIG_ROLE")
            home = _resolve_role_home(resolved_role, self._base_env)
            if home is not None:
                env["LOGION_HOME"] = str(home)
                # The rig installs the built wheel and the npm wrapper into
                # the role tree; `activate.sh` puts both on PATH for an
                # interactive shell. An agent gets no such shell, so a hook
                # firing `logion` would find nothing. Wire the same two
                # directories here so the run exercises the installed
                # artifact rather than the source checkout.
                env["PATH"] = _role_tree_path(home.parent)
            api_key = role_keys.api_key(resolved_role)
            if api_key:
                env["LOGION_API_KEY"] = api_key
            agent_env[agent_id] = env
        baseline = {}
        if role_keys.configured:
            baseline = await LogionApiQueries(
                self._base_env["LOGION_API_BASE_URL"], role_keys
            ).baseline(agent_roles or {})

        return World(
            run_id=run_id,
            base_url=self._base_env["LOGION_API_BASE_URL"],
            root_dir=self._root,
            agent_env=agent_env,
            handles={aid: f"agent_{aid}" for aid in agent_ids},
            data={
                "devrig_env": env_file_description(self._base_env),
                "api_log_present": self._api_log_path.is_file(),
                "agent_roles": agent_roles or {},
                "baseline": baseline,
            },
        )

    async def snapshot(
        self,
        world: World,  # noqa: ARG002
    ) -> JsonObject:
        snapshot: JsonObject = {
            "base_url": self._base_env.get("LOGION_API_BASE_URL"),
            "devrig_env": env_file_description(self._base_env),
        }
        if self._api_log_path.is_file():
            snapshot["api_log_tail"] = _tail_text(self._api_log_path, 200)
        return snapshot

    async def query(
        self,
        world: World,
        query: JsonObject,
    ) -> JsonObject:
        query_type = query.get("type")
        if query_type == "health_ok":
            try:
                await health_check_endpoint(
                    self._base_env["LOGION_API_BASE_URL"]
                )
            except HealthCheckError as exc:
                return {"found": False, "error": str(exc)}
            return {"found": True, "evidence": {"source": "api"}}
        if query_type == "api_log_present":
            return {
                "found": self._api_log_path.is_file(),
                "path": str(self._api_log_path),
            }
        if query_type in {
            "runner_enrolled",
            "runner_job_completed",
            "runner_receipt_published",
            "runner_job_terminal_once",
        }:
            return _runner_fact_query(query_type, query)
        agent_roles = world.data.get("agent_roles") or {}
        role_keys = _role_key_store_from_devrig(
            self._base_env, list(world.agent_env.keys()), agent_roles
        )
        if role_keys.configured:
            query_with_baseline = {
                **query,
                "_baseline": world.data.get("baseline") or {},
            }
            queries = LogionApiQueries(
                self._base_env["LOGION_API_BASE_URL"], role_keys
            )
            return await queries.query(query_with_baseline, dict(agent_roles))
        return {
            "found": False,
            "unsupported": True,
            "reason": (
                "local-devrig adapter has no proving-ground API keys; "
                "set LOGION_PROVING_GROUND_ROLE_KEYS_FILE or LOGION_API_KEY "
                "to enable observed-effect queries"
            ),
        }

    async def stop(self) -> None:
        pass


def _role_key_store_from_devrig(
    base_env: dict[str, str],
    agent_ids: list[str],
    agent_roles: dict[str, str],
) -> RoleKeyStore:
    """Build a RoleKeyStore from env hints and workspace devrig files."""
    roles: dict[str, dict[str, str]] = {}
    desired_roles = list(
        dict.fromkeys([
            *agent_roles.values(),
            *(agent_roles.get(agent_id) for agent_id in agent_ids),
            base_env.get("LOGION_DEVRIG_ROLE", "seller"),
            "seller",
            "buyer",
            "admin",
        ])
    )

    env_store = RoleKeyStore.from_env(base_env)
    for role in desired_roles:
        if not role:
            continue
        role_entry = _read_role_entry(role, base_env)
        if role_entry:
            roles[role] = role_entry
            continue
        api_key = env_store.api_key(role)
        if api_key:
            entry: dict[str, str] = {"api_key": api_key}
            agent_id = env_store.agent_id(role)
            if agent_id:
                entry["agent_id"] = agent_id
            roles[role] = entry

    return RoleKeyStore(roles)


def _role_tree_path(role_tree: Path) -> str:
    """Prepend a role tree's installed CLI directories to the host PATH."""
    dirs = [role_tree / "pipx-bin", role_tree / "npm-prefix" / "bin"]
    present = [str(path) for path in dirs if path.is_dir()]
    return os.pathsep.join([*present, os.environ.get("PATH", "")])


def _resolve_role_home(
    role: str | None, base_env: dict[str, str]
) -> Path | None:
    if not role:
        return None
    for devrig_root in _workspace_devrig_roots(base_env):
        home = devrig_root / role / "logion-home"
        if home.is_dir():
            return home
    return None


def _read_role_entry(
    role: str,
    base_env: dict[str, str],
) -> dict[str, str] | None:
    home = _resolve_role_home(role, base_env)
    credentials = _read_credentials(home) if home else None
    api_key = credentials.get("api_key") if credentials else None
    for devrig_root in _workspace_devrig_roots(base_env):
        key_file = devrig_root / role / ".api-key"
        try:
            text = key_file.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if text:
            api_key = api_key or text
            break
    if not api_key:
        return None
    entry: dict[str, str] = {"api_key": api_key}
    if credentials and credentials.get("agent_id"):
        entry["agent_id"] = credentials["agent_id"]
    return entry


def _workspace_devrig_roots(base_env: dict[str, str]) -> list[Path]:
    candidates: list[Path] = []

    def _add(path: Path | None) -> None:
        if path is None:
            return
        resolved = path.expanduser().resolve()
        if resolved.is_dir() and resolved not in candidates:
            candidates.append(resolved)

    role_keys_file = os.environ.get("LOGION_PROVING_GROUND_ROLE_KEYS_FILE")
    if role_keys_file:
        _add(Path(role_keys_file).expanduser().resolve().parent)

    home_value = os.environ.get("LOGION_HOME") or base_env.get("LOGION_HOME")
    if home_value:
        home_path = Path(home_value).expanduser().resolve()
        if home_path.name == "logion-home" and len(home_path.parents) >= 2:
            _add(home_path.parents[1])

    public_repo_path = os.environ.get(
        "LOGION_PUBLIC_REPO_PATH"
    ) or base_env.get("LOGION_PUBLIC_REPO_PATH")
    if public_repo_path:
        repo_root = Path(public_repo_path).expanduser().resolve()
        _add(repo_root / ".devrig")
        _add(repo_root.parent / ".devrig")

    return candidates


def _read_credentials(home_path: Path | None) -> dict[str, str] | None:
    if home_path is None:
        return None
    try:
        path = home_path.expanduser().resolve() / "credentials.json"
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, KeyError):
        return None
    if not isinstance(data, dict):
        return None
    api_key = data.get("api_key")
    if not api_key:
        return None
    result: dict[str, str] = {"api_key": str(api_key)}
    agent_id = data.get("agent_id")
    if agent_id:
        result["agent_id"] = str(agent_id)
    return result


def _resolve_devrig_root(explicit: Path | str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env_root = _env_root()
    if env_root:
        return env_root
    cwd = Path.cwd().resolve()
    if (cwd / "scripts" / "devrig.py").is_file() and (
        cwd / ".devrig" / "devrig.env"
    ).is_file():
        return cwd
    for parent in cwd.parents:
        if (parent / "scripts" / "devrig.py").is_file() and (
            parent / ".devrig" / "devrig.env"
        ).is_file():
            return parent
    raise DevrigEnvError(
        "local-devrig adapter could not find a public logion repo root. "
        "Pass --devrig-root or set LOGION_PUBLIC_REPO_PATH."
    )


def _env_root() -> Path | None:
    value = os.environ.get("LOGION_PUBLIC_REPO_PATH")
    if value:
        candidate = Path(value).expanduser().resolve()
        if (candidate / "scripts" / "devrig.py").is_file():
            return candidate
    return None


def _tail_text(path: Path, max_bytes: int = 65536) -> str:
    try:
        with path.open("rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            if size <= max_bytes:
                f.seek(0)
            else:
                f.seek(-max_bytes, os.SEEK_END)
            data = f.read()
    except OSError:
        return ""
    return data.decode("utf-8", errors="replace")


def _resolve_api_log_path(root: Path, explicit: Path | str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env_path = os.environ.get("LOGION_PROVING_GROUND_API_LOG_PATH")
    if env_path:
        return Path(env_path).expanduser().resolve()
    for devrig_root in _workspace_devrig_roots({}):
        candidate = devrig_root / "api.log"
        if candidate.is_file():
            return candidate
    for name in ("api.log", "prism.log"):
        candidate = root / ".devrig" / name
        if candidate.is_file():
            return candidate
    return root / ".devrig" / "api.log"


_RUNNER_QUERY_FACTS: dict[str, tuple[str, ...]] = {
    "runner_enrolled": (
        "runner_id",
        "runner_key_fingerprint",
        "runner_import_root",
        "runner_credential_kind",
        "runner_package_version",
    ),
    "runner_job_completed": (
        "job_id",
        "terminal_status",
        "attempt_count",
        "uploaded_artifact_digest",
        "coordinator_artifact_digest",
        "lease_holder",
    ),
    "runner_receipt_published": (
        "receipt_id",
        "receipt_digest",
        "coordinator_accepted",
        "accepted_as_late_evidence",
        "published_at",
    ),
    "runner_job_terminal_once": (
        "terminal_transition_count",
        "terminal_status",
        "duplicate_receipt_rejected",
        "attempt_count",
    ),
}


def _load_runner_manifest(
    raw_path: object, assertion: str
) -> tuple[JsonObject | None, str]:
    """Read the retained manifest, scoped to *assertion*.

    Returns ``(facts, path)`` on success and ``(None, reason)`` otherwise.
    Three 15.15 contracts name a fact ``terminal_status`` over three
    different keyspaces, so the manifest is scoped by assertion type; a
    flat manifest is still read, for evidence sealed before the scoping.
    """
    if not isinstance(raw_path, str) or not raw_path:
        return None, "unavailable"
    path = Path(raw_path)
    try:
        if path.is_symlink() or not path.is_file():
            return None, "unavailable"
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"runner evidence unreadable: {exc}"
    if not isinstance(payload, dict) or not isinstance(
        payload.get("facts"), dict
    ):
        return None, "runner evidence has no typed facts"
    facts = payload["facts"]
    scoped = facts.get(assertion)
    return (scoped if isinstance(scoped, dict) else facts), str(path)


def _runner_fact_result(
    facts: JsonObject, required: object, path: str
) -> JsonObject:
    """Decide found/complete from what the manifest actually retained."""
    names = required if isinstance(required, (list, tuple)) else []
    selected = {name: facts.get(name) for name in names}
    complete = all(
        isinstance(value, dict)
        and value.get("ok") is True
        and "value" in value
        for value in selected.values()
    )
    return {
        "found": complete,
        "facts": selected,
        "evidence": {"source": "retained-runner-manifest", "path": path},
        **(
            {}
            if complete
            else {"reason": "required typed runner facts are missing"}
        ),
    }


def _runner_fact_query(query_type: object, query: JsonObject) -> JsonObject:
    """Return only typed facts captured by the retained runner manifest.

    A missing manifest is a real capability gap and is the only path that
    returns ``unsupported``. Malformed or incomplete captured data is a
    failed observation, never an excuse to turn a required assertion into
    a skip.
    """
    assertion = str(query_type)
    required = _RUNNER_QUERY_FACTS.get(assertion)
    if required is None:
        return {
            "found": False,
            "unsupported": True,
            "reason": "unknown runner query",
        }
    facts, detail = _load_runner_manifest(query.get("manifest"), assertion)
    if facts is None:
        if detail == "unavailable":
            return {
                "found": False,
                "unsupported": True,
                "reason": ("retained runner evidence manifest is unavailable"),
            }
        return {"found": False, "reason": detail}
    return _runner_fact_result(facts, required, detail)
