#!/usr/bin/env python3
"""Capture the sandbox evidence the 15.14.1 scenario asserts on.

Runs on the operator side (the host driving Compose), never inside a
role. For each requested role it probes the live container with
``docker compose exec`` and writes one JSON manifest per phase:

- identity/limits: the role's UID and the runtime's declared limits;
- canaries: probes that must be unreadable from inside a role (host
  home, cross-role home, Docker socket, keychain);
- repository scope: where a checked-in fixture skill landed after the
  consumer installed it;
- selective reset: which role's state/key survived the reset.

Every claim the gate makes is a fact a hook captured, not prose an
agent agreed to.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

NODE_DIR = Path(__file__).resolve().parents[3] / "deploy" / "local-node"
COMPOSE = (
    "docker",
    "compose",
    "--project-directory",
    str(NODE_DIR),
    "-f",
    str(NODE_DIR / "compose.yaml"),
)
EXPECTED_UIDS = {"consumer": 10001, "auditor": 10002}


def _runtime() -> str:
    return os.environ.get("CONTAINER_RUNTIME", "docker")


def _compose(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    runtime = _runtime()
    command = [*COMPOSE, *args]
    command[0] = runtime
    container_host = (
        "host.containers.internal"
        if runtime == "podman"
        else "host.docker.internal"
    )
    env = {
        **os.environ,
        "LOGION_NODE_IMAGE": os.environ.get(
            "LOGION_NODE_IMAGE", "logion-local-node-role:latest"
        ),
        "LOGION_BASE_URL": os.environ.get(
            "LOGION_BASE_URL", "http://localhost:8000"
        ),
        "LOGION_CONTAINER_BASE_URL": os.environ.get(
            "LOGION_CONTAINER_BASE_URL", f"http://{container_host}:8000"
        ),
        "ROLE_WALL_TIME_SECONDS": os.environ.get(
            "ROLE_WALL_TIME_SECONDS", "3600"
        ),
    }
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=check,
        env=env,
    )


def _container_id(role: str) -> str:
    result = _compose("ps", "-q", role, check=False)
    return result.stdout.strip()


def _inspect(role: str) -> dict:
    container_id = _container_id(role)
    if not container_id:
        return {}
    result = subprocess.run(
        [_runtime(), "inspect", container_id],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return {}
    payload = json.loads(result.stdout)
    return payload[0] if isinstance(payload, list) and payload else {}


def _exec(role: str, command: list[str]) -> tuple[int, str]:
    """Run a command inside one role; return (exit_code, stdout)."""
    result = _compose("exec", "-T", role, *command, check=False)
    return result.returncode, result.stdout.strip()


def _role_limits(
    inspect: dict, role: str
) -> dict[str, float | int | bool | None]:
    """Read the runtime's actual cgroup/inspect facts for one role."""
    host_config = inspect.get("HostConfig", {})
    config = inspect.get("Config", {})
    nano_cpus = host_config.get("NanoCpus")
    command = " ".join(str(item) for item in config.get("Cmd", []))
    env = config.get("Env", [])
    wall_time = next(
        (
            int(value.split("=", 1)[1])
            for value in env
            if value.startswith("ROLE_WALL_TIME_SECONDS=")
        ),
        None,
    )
    _rc, pids_text = _exec(
        role,
        ["sh", "-c", "cat /sys/fs/cgroup/pids.max 2>/dev/null || echo max"],
    )
    _rc, mem_text = _exec(
        role,
        ["sh", "-c", "cat /sys/fs/cgroup/memory.max 2>/dev/null || echo max"],
    )
    timeout_probe_rc, _ = _exec(role, ["timeout", "0.05", "sleep", "1"])
    return {
        "cpus": nano_cpus / 1_000_000_000
        if isinstance(nano_cpus, int) and nano_cpus
        else None,
        "memory_bytes": int(mem_text) if mem_text.isdigit() else None,
        "pids": int(pids_text) if pids_text.isdigit() else None,
        "wall_time_seconds": wall_time,
        "wall_time_probe_exit_code": timeout_probe_rc,
        "wall_time_enforced": bool(
            wall_time
            and "timeout --signal=TERM" in command
            and timeout_probe_rc == 124
        ),
    }


def _role_identity_facts(role: str) -> tuple[str | None, str | None]:
    """Identity, agent id, and non-secret credential fingerprint per role."""
    identity_path = NODE_DIR / "roles" / f"{role}.identity.json"
    agent_id: str | None = None
    if identity_path.exists():
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        agent_id = identity.get("agent_id")
    key_path = NODE_DIR / "roles" / f"{role}.api_key"
    fingerprint = (
        hashlib.sha256(key_path.read_bytes()).hexdigest()[:16]
        if key_path.exists()
        else None
    )
    return agent_id, fingerprint


def _scenario_prompts() -> list[dict[str, str]]:
    """Retain the exact phase goals agents were given (no secrets)."""
    scenario_path = (
        Path(__file__).resolve().parents[1]
        / "agent_proving_ground"
        / "scenarios"
        / "builtin"
        / "local_multi_agent_node.yaml"
    )
    try:
        import yaml

        scenario = yaml.safe_load(scenario_path.read_text(encoding="utf-8"))
        return [
            {
                "phase_id": phase["id"],
                "actor": phase["actor"],
                "goal": phase["goal"],
            }
            for phase in scenario.get("phases", [])
            if phase.get("goal")
        ]
    except (OSError, TypeError, ValueError):
        return []


def _role_entry(role: str) -> dict:
    """Collect one role's runtime identity, limits, and version facts."""
    rc, uid_text = _exec(role, ["id", "-u"])
    uid = int(uid_text) if rc == 0 and uid_text.isdigit() else None
    inspect = _inspect(role)
    versions = {}
    for name, cmd in {
        "logion": ["logion", "--version"],
        "codex": ["codex", "--version"],
        "git": ["git", "--version"],
    }.items():
        version_rc, version = _exec(role, cmd)
        versions[name] = version if version_rc == 0 else "unavailable"
    mounts = [
        {
            "type": mount.get("Type"),
            "name": mount.get("Name"),
            "destination": mount.get("Destination"),
            "rw": mount.get("RW"),
        }
        for mount in inspect.get("Mounts", [])
    ]
    home_rc, _ = _exec(
        role,
        [
            "sh",
            "-c",
            "touch /home/agent/.write-probe && rm /home/agent/.write-probe",
        ],
    )
    return {
        "uid": uid,
        "home_writable": home_rc == 0,
        "expected_uid": EXPECTED_UIDS.get(role),
        "user": _exec(role, ["id", "-un"])[1],
        "container_id": _container_id(role),
        "image_id": inspect.get("Image"),
        "limits": _role_limits(inspect, role),
        "versions": versions,
        "mounts": mounts,
    }


def capture_identity_and_limits(roles: list[str], out: Path) -> None:
    entries: dict[str, dict] = {}
    role_agent_ids: dict[str, str | None] = {}
    credential_fingerprints: dict[str, str | None] = {}
    for role in roles:
        entries[role] = _role_entry(role)
        agent_id, fingerprint = _role_identity_facts(role)
        role_agent_ids[role] = agent_id
        credential_fingerprints[role] = fingerprint
    prompts = _scenario_prompts()
    compose_bytes = (NODE_DIR / "compose.yaml").read_bytes()
    dockerfile_bytes = (NODE_DIR / "Dockerfile.role").read_bytes()
    out.write_text(
        json.dumps(
            {
                "roles": entries,
                "runtime": _runtime(),
                "compose_sha256": hashlib.sha256(compose_bytes).hexdigest(),
                "dockerfile_sha256": hashlib.sha256(
                    dockerfile_bytes
                ).hexdigest(),
                "role_agent_ids": role_agent_ids,
                "credential_fingerprints": credential_fingerprints,
                "prompts": prompts,
            },
            indent=2,
        )
        + "\n"
    )


def capture_canaries(roles: list[str], out: Path) -> None:
    canaries: dict[str, dict] = {}
    # Seed unique values at the REAL home/spool/workspace locations. A peer
    # probe greps for the other role's value at its mounted target, so a shared
    # volume is detected instead of merely checking an invented path.
    for role in roles:
        seed_rc, _ = _exec(
            role,
            [
                "sh",
                "-c",
                f"printf '%s' '{role}-home-canary' > "
                "/home/agent/isolation-canary && "
                f"printf '%s' '{role}-spool-canary' > "
                "/home/agent/.logion/spool/isolation-canary && "
                f"printf '%s' '{role}-workspace-canary' > "
                "/workspace/isolation-canary",
            ],
        )
        if seed_rc != 0:
            raise SystemExit(f"cannot seed real canary paths for {role}")
    for role in roles:
        peer = next(item for item in roles if item != role)
        commands = {
            "host_home": "test -d /Users && echo PRESENT || echo ABSENT",
            "host_keychain": (
                "test -e /home/agent/Library/Keychains/login.keychain-db "
                "-o -e /Library/Keychains/System.keychain "
                "&& echo PRESENT || echo ABSENT"
            ),
            "docker_socket": (
                "test -S /var/run/docker.sock && echo PRESENT || echo ABSENT"
            ),
            "peer_home": (
                f"grep -q '{peer}-home-canary' /home/agent/isolation-canary "
                "2>/dev/null && echo PRESENT || echo ABSENT"
            ),
            "peer_credential": (
                f"test -r /run/secrets/{peer}_api_key "
                "&& echo PRESENT || echo ABSENT"
            ),
            "peer_spool": (
                f"grep -q '{peer}-spool-canary' "
                "/home/agent/.logion/spool/isolation-canary "
                "2>/dev/null && echo PRESENT || echo ABSENT"
            ),
            "peer_workspace": (
                f"grep -q '{peer}-workspace-canary' "
                "/workspace/isolation-canary "
                "2>/dev/null && echo PRESENT || echo ABSENT"
            ),
        }
        for name, command in commands.items():
            rc, text = _exec(role, ["sh", "-c", command])
            canaries[f"{role}_sees_{name}"] = {
                "readable": rc == 0 and text == "PRESENT",
                "role": role,
                "peer": peer if name.startswith("peer_") else None,
            }
    out.write_text(json.dumps({"canaries": canaries}, indent=2) + "\n")


def capture_repository_scope(out: Path) -> None:
    """Where did the fixture land after the consumer's repo install?"""
    visible, in_abc, user_scope, auditor_scope = False, False, False, False
    rc, text = _exec(
        "consumer",
        [
            "sh",
            "-c",
            "test -d /workspace/xpto/.logion-home/installed/fixture-skill "
            "&& echo yes || echo no",
        ],
    )
    visible = text == "yes" and rc == 0
    rc, text = _exec(
        "consumer",
        [
            "sh",
            "-c",
            "test -d /workspace/abc/.logion-home/installed/fixture-skill "
            "&& echo yes || echo no",
        ],
    )
    in_abc = text == "yes"
    rc, text = _exec(
        "consumer",
        [
            "sh",
            "-c",
            'test -d "$LOGION_HOME/installed/fixture-skill" '
            "&& echo yes || echo no",
        ],
    )
    user_scope = text == "yes"
    rc, text = _exec(
        "auditor",
        [
            "sh",
            "-c",
            "test -d /workspace/xpto/.logion-home/installed/fixture-skill "
            "&& echo yes || echo no",
        ],
    )
    auditor_scope = text == "yes"
    out.write_text(
        json.dumps(
            {
                "repository_scope": {
                    "visible_in_xpto": visible,
                    "absent_from_abc": not in_abc,
                    "absent_from_user_scope": not user_scope,
                    "absent_from_auditor": not auditor_scope,
                },
            },
            indent=2,
        )
        + "\n"
    )


def _b64(content: str) -> str:
    return base64.b64encode(content.encode("utf-8")).decode("ascii")


def seed_node_workspaces(out: Path) -> None:  # noqa: ARG001
    """Seed fixture + repository checkouts inside the node containers.

    The role workspaces are named volumes, empty on first run; the
    fixture bundle and the XPTO/ABC checkouts must exist inside the
    containers before the install phase can be repository-scoped.
    Files are written as the role's own user via base64 exec: a host
    side ``docker cp`` lands with host ownership the role cannot read,
    which is exactly the cross-identity leak this node exists to
    prevent. The bundle satisfies ``validate_course_bundle`` so the
    install is a real install. Idempotent: re-running a phase
    rewrites the same bytes.
    """
    files = {
        "SKILL.md": (
            "---\n"
            "name: fixture-skill\n"
            "description: Repository-scope fixture for the local node smoke\n"
            "---\n\n"
            "# fixture-skill\n\n"
            "Proves installs can be scoped to a repository checkout.\n"
        ),
        "LICENSE": "MIT\n",
        "course/capabilities.yaml": "capabilities: []\n",
    }
    for role in ("consumer", "auditor"):
        _exec(
            role,
            [
                "sh",
                "-c",
                "rm -rf /workspace/fixtures/fixture-skill && "
                "mkdir -p /workspace/xpto /workspace/abc "
                "/workspace/fixtures/fixture-skill/course",
            ],
        )
        for rel, content in files.items():
            rc, _ = _exec(
                role,
                [
                    "sh",
                    "-c",
                    f"echo {_b64(content)} | base64 -d > "
                    f"/workspace/fixtures/fixture-skill/{rel}",
                ],
            )
            if rc != 0:
                raise SystemExit(
                    f"fixture seed failed in {role}: cannot write {rel}"
                )
        rc, text = _exec(
            role,
            [
                "sh",
                "-c",
                "test -f /workspace/fixtures/fixture-skill/SKILL.md "
                "&& echo ok || echo missing",
                "|| echo missing",
            ],
        )
        if rc != 0 or text != "ok":
            raise SystemExit(
                f"fixture seed failed in {role}: SKILL.md missing"
            )
    sys.stdout.write(json.dumps({"seeded": ["consumer", "auditor"]}) + "\n")


def _probe_http(role: str, attempts: int = 10) -> str:
    """Probe the API from inside a role, retrying until stable.

    A single-shot curl right after `node-dev-up` races the container
    start and the network attach; a probe that would flake is not
    evidence. Retries read the same fact until it is stable.
    """
    # The re-up may have recreated the role's container; wait for the
    # container to actually be running before the first probe.
    for _ in range(attempts):
        state = subprocess.run(
            [
                _runtime(),
                "inspect",
                "--format",
                "{{.State.Running}}",
                f"logion-local-node-{role}-1",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if state.stdout.strip() == "true":
            break
        time.sleep(1)
    code = "000"
    for _ in range(attempts):
        rc, code = _exec(
            role,
            [
                "sh",
                "-c",
                'curl -s -o /dev/null -w "%{http_code}" '
                '-H "Authorization: Bearer $(cat /run/secrets/'
                + role
                + '_api_key 2>/dev/null)" '
                '"$LOGION_BASE_URL/v1/notifications"',
            ],
        )
        if rc == 0 and code in {"200", "401", "403"}:
            return code
        time.sleep(2)
    return code


def capture_selective_reset(out: Path, cred_path: Path | None = None) -> None:
    """Use the delivered reset command, then prove revocation and isolation."""
    repo_root = NODE_DIR.parent.parent
    old_key_path = NODE_DIR / "roles" / "consumer.api_key"
    old_key = old_key_path.read_text(encoding="utf-8").strip()
    old_fingerprint = hashlib.sha256(old_key.encode()).hexdigest()[:16]
    reset = subprocess.run(
        ["make", "node-dev-reset", "ROLE=consumer", "YES=1"],
        capture_output=True,
        text=True,
        cwd=repo_root,
        check=False,
    )
    req = requests.get(
        os.environ.get("LOGION_BASE_URL", "http://localhost:8000").rstrip("/")
        + "/v1/notifications",
        headers={"Authorization": f"Bearer {old_key}"},
        timeout=30,
    )
    consumer_key_rejected = req.status_code in {401, 403}
    up = subprocess.run(
        ["make", "node-dev-up", "ROLES=consumer,auditor"],
        capture_output=True,
        text=True,
        cwd=repo_root,
        check=False,
    )
    rc, text = _exec(
        "consumer",
        ["sh", "-c", "test -d /workspace/xpto && echo present || echo gone"],
    )
    consumer_state_removed = rc == 0 and text == "gone"
    rc, text = _exec(
        "auditor",
        ["sh", "-c", "test -d /workspace/abc && echo present || echo gone"],
    )
    auditor_state_preserved = rc == 0 and text == "present"
    consumer_new_key_accepted = _probe_http("consumer") == "200"
    auditor_key_accepted = _probe_http("auditor") == "200"
    if cred_path is not None and Path(cred_path).exists():
        cred = json.loads(cred_path.read_text(encoding="utf-8"))
        credentials = cred.get("credentials", {})
        credentials.setdefault("consumer", {})["revoked_key_rejected"] = (
            consumer_key_rejected
        )
        credentials["consumer"]["new_key_works_after_reset"] = (
            consumer_new_key_accepted
        )
        credentials.setdefault("auditor", {})["key_works_after_reset"] = (
            auditor_key_accepted
        )
        cred["credentials"] = credentials
        cred_path.write_text(json.dumps(cred, indent=2) + "\n")
    out.write_text(
        json.dumps(
            {
                "selective_reset": {
                    "consumer_state_removed": consumer_state_removed,
                    "consumer_key_rejected": consumer_key_rejected,
                    "consumer_new_key_accepted": consumer_new_key_accepted,
                    "auditor_state_preserved": auditor_state_preserved,
                    "auditor_key_accepted": auditor_key_accepted,
                    "old_credential_fingerprint": old_fingerprint,
                    "reset_exit_code": reset.returncode,
                    "up_exit_code": up.returncode,
                }
            },
            indent=2,
        )
        + "\n"
    )


def provision_credentials(out: Path) -> None:
    """Verify node-up provisioned distinct, server-issued role identities."""
    identities: dict[str, dict] = {}
    for role in ("consumer", "auditor"):
        identity_path = NODE_DIR / "roles" / f"{role}.identity.json"
        key_path = NODE_DIR / "roles" / f"{role}.api_key"
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        identities[role] = {
            "agent_id": identity.get("agent_id"),
            "user_id": identity.get("user_id"),
            "credential_fingerprint": hashlib.sha256(
                key_path.read_bytes()
            ).hexdigest()[:16],
        }
    if identities["consumer"]["agent_id"] == identities["auditor"]["agent_id"]:
        raise SystemExit("role identities are not distinct")
    out.write_text(json.dumps({"identities": identities}, indent=2) + "\n")
    sys.stdout.write(json.dumps({"provisioned": sorted(identities)}) + "\n")


def capture_credentials(out: Path) -> None:
    """Per-role identity, non-secret fingerprint, and live key status."""
    credentials: dict[str, dict] = {}
    for role in ("consumer", "auditor"):
        identity_path = NODE_DIR / "roles" / f"{role}.identity.json"
        key_path = NODE_DIR / "roles" / f"{role}.api_key"
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        key_works = _probe_http(role) == "200"
        credentials[role] = {
            "agent_id": identity.get("agent_id"),
            "credential_fingerprint": hashlib.sha256(
                key_path.read_bytes()
            ).hexdigest()[:16],
            "key_works_before_reset": key_works,
        }
    out.write_text(json.dumps({"credentials": credentials}, indent=2) + "\n")


def capture_restart(out: Path) -> None:
    """Mechanically stop/start the node between marker snapshots."""

    def markers() -> dict[str, str]:
        result: dict[str, str] = {}
        for role in ("consumer", "auditor"):
            rc, text = _exec(
                role,
                [
                    "sh",
                    "-c",
                    'cat "$LOGION_HOME/node-state-marker" 2>/dev/null',
                ],
            )
            result[role] = text if rc == 0 and text else f"unreachable:{role}"
        return result

    repo_root = NODE_DIR.parent.parent
    before = markers()
    before_ids = {
        role: _container_id(role) for role in ("consumer", "auditor")
    }
    down = subprocess.run(
        ["make", "node-dev-down"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    up = subprocess.run(
        ["make", "node-dev-up", "ROLES=consumer,auditor"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    after_ids = {role: _container_id(role) for role in ("consumer", "auditor")}
    after = markers()
    _rc, text = _exec(
        "auditor",
        [
            "sh",
            "-c",
            'grep -q consumer "$LOGION_HOME/node-state-marker" '
            "2>/dev/null && echo yes || echo no",
        ],
    )
    restart = {
        "performed": down.returncode == 0 and up.returncode == 0,
        "down_exit_code": down.returncode,
        "up_exit_code": up.returncode,
        "container_ids_before": before_ids,
        "container_ids_after": after_ids,
        "container_ids_changed": all(
            before_ids[role]
            and after_ids[role]
            and before_ids[role] != after_ids[role]
            for role in ("consumer", "auditor")
        ),
    }
    out.write_text(
        json.dumps(
            {
                "before_restart": before,
                "after_restart": after,
                "marker_sha256": {
                    "before": {
                        role: hashlib.sha256(value.encode()).hexdigest()
                        for role, value in before.items()
                    },
                    "after": {
                        role: hashlib.sha256(value.encode()).hexdigest()
                        for role, value in after.items()
                    },
                },
                "cross_role_visible": text == "yes",
                "restart": restart,
            },
            indent=2,
        )
        + "\n"
    )


def capture_harness_use(out: Path) -> None:
    """Run Codex in each role and require a Logion-produced artifact."""
    results: dict[str, dict] = {}
    for role in ("consumer", "auditor"):
        proof = "/workspace/task/harness-proof.txt"
        _exec(role, ["rm", "-f", proof])
        prompt = (
            "Use the shell exactly once to run: logion --version > "
            f"{proof} && printf '\nLOGION_HARNESS_OK {role}\n' >> {proof}. "
            "Then report completion without changing any other file."
        )
        process = _compose(
            "exec",
            "-T",
            role,
            "codex-role",
            "exec",
            "--skip-git-repo-check",
            "--dangerously-bypass-approvals-and-sandbox",
            "--model",
            "gpt-5.4-mini",
            prompt,
            check=False,
        )
        rc, proof_text = _exec(role, ["sh", "-c", f"cat {proof} 2>/dev/null"])
        results[role] = {
            "process_exit_code": process.returncode,
            "proof_read_exit_code": rc,
            "proof": proof_text,
            "prompt": prompt,
            "codex_version": _exec(role, ["codex", "--version"])[1],
        }
    out.write_text(json.dumps({"harness_runs": results}, indent=2) + "\n")


def main() -> int:
    capture = sys.argv[1]
    out = Path(sys.argv[2]).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    if capture == "identity":
        capture_identity_and_limits(["consumer", "auditor"], out)
    elif capture == "canaries":
        capture_canaries(["consumer", "auditor"], out)
    elif capture == "repository_scope":
        capture_repository_scope(out)
    elif capture == "seed_node_workspaces":
        seed_node_workspaces(out)
    elif capture == "provision_credentials":
        provision_credentials(out)
    elif capture == "credentials":
        capture_credentials(out)
    elif capture == "restart":
        capture_restart(out)
    elif capture == "harness_use":
        capture_harness_use(out)
    elif capture == "selective_reset":
        cred = Path(sys.argv[3]) if len(sys.argv) > 3 else None
        capture_selective_reset(out, cred)
    else:
        raise SystemExit(f"unknown capture: {capture}")
    sys.stdout.write(json.dumps({"evidence_manifest": str(out)}) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
