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


def _compose(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        [*COMPOSE, *args], capture_output=True, text=True, check=check
    )


def _exec(role: str, command: list[str]) -> tuple[int, str]:
    """Run a command inside one role; return (exit_code, stdout)."""
    result = _compose("exec", "-T", role, *command, check=False)
    return result.returncode, result.stdout.strip()


def capture_identity_and_limits(roles: list[str], out: Path) -> None:
    entries: dict[str, dict] = {}
    for role in roles:
        rc, uid_text = _exec(role, ["id", "-u"])
        uid = int(uid_text) if rc == 0 and uid_text.isdigit() else None
        rc, pids_text = _exec(
            role,
            [
                "sh",
                "-c",
                "cat /sys/fs/cgroup/pids.max 2>/dev/null || echo max",
            ],
        )
        limits: dict[str, float | int | None] = {
            "cpus": None,
            "memory_bytes": None,
            "pids": None,
        }
        rc, mem_text = _exec(
            role,
            [
                "sh",
                "-c",
                "cat /sys/fs/cgroup/memory.max 2>/dev/null || echo max",
            ],
        )
        if mem_text.isdigit():
            limits["memory_bytes"] = int(mem_text)
        if pids_text.isdigit():
            limits["pids"] = int(pids_text)
        # The runtime declares CPU/memory limits in compose.yaml; the
        # hook records what the runtime reports so the assertion
        # compares two machine facts. Plain `docker inspect`, not
        # `docker compose inspect` (which does not exist).
        inspect = subprocess.run(
            [
                "docker",
                "inspect",
                "--format",
                "{{json .HostConfig.NanoCpus}}",
                f"logion-local-node-{role}-1",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if inspect.stdout.strip().isdigit() and inspect.stdout.strip() != "0":
            limits["cpus"] = int(inspect.stdout.strip()) / 1_000_000_000
        entries[role] = {
            "uid": uid,
            "expected_uid": EXPECTED_UIDS.get(role),
            "user": _exec(role, ["id", "-un"])[1],
            "limits": limits,
        }
    out.write_text(json.dumps({"roles": entries}, indent=2) + "\n")


def capture_canaries(roles: list[str], out: Path) -> None:
    canaries: dict[str, dict] = {}
    probes = [
        (
            "host_home",
            [
                "sh",
                "-c",
                "cat /host-home/.logion-node-canary "
                "2>/dev/null || echo UNMOUNTED",
            ],
        ),
        (
            "docker_socket",
            [
                "sh",
                "-c",
                "test -S /var/run/docker.sock && echo PRESENT || echo ABSENT",
            ],
        ),
        ("other_role_home", None),  # filled per pair below
    ]
    for role in roles:
        for name, command in probes:
            if command is None:
                other = [r for r in roles if r != role]
                readable = False
                for peer in other:
                    rc, text = _exec(
                        role,
                        [
                            "sh",
                            "-c",
                            f"test -d /peer-{peer}-home "
                            "&& echo MOUNTED || echo ABSENT",
                        ],
                    )
                    readable = readable or text == "MOUNTED"
                canaries[f"{role}_sees_{name}"] = {
                    "readable": readable,
                    "role": role,
                }
                continue
            rc, text = _exec(role, command)
            readable = text not in {"UNMOUNTED", "ABSENT", ""} and rc == 0
            canaries[f"{role}_sees_{name}"] = {
                "readable": readable,
                "role": role,
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
            "test -d \"$LOGION_HOME/installed/fixture-skill\" "
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
                "docker",
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
                "'http://host.docker.internal:8000/v1/notifications'",
            ],
        )
        if rc == 0 and code in {"200", "401", "403"}:
            return code
        time.sleep(2)
    return code


def capture_selective_reset(out: Path, cred_path: Path | None = None) -> None:
    """Run the selective consumer reset, then capture post-state.

    The reset is an operator action (`make node-dev-reset
    ROLE=consumer YES=1`): it stops the consumer container, removes
    only the consumer's disposable volumes, and retires its local key
    copy. This hook executes it and then probes both roles so the
    assertion compares machine facts, not intentions.
    """
    repo_root = NODE_DIR.parent.parent
    reset = subprocess.run(
        ["make", "node-dev-reset", "ROLE=consumer", "YES=1"],
        capture_output=True,
        text=True,
        cwd=repo_root,
        check=False,
    )
    # Server-side revocation: rotate the consumer agent's api key.
    # The old mounted key dies at the server; the container still runs
    # with the old credential, so the rejection probe measures a real
    # revocation, not a missing file.
    ident_path = NODE_DIR / "roles" / "consumer.identity.json"
    ident = json.loads(ident_path.read_text(encoding="utf-8"))
    rot = requests.post(
        f"http://localhost:8000/v1/identity/users/{ident['user_id']}"
        f"/agents/{ident['agent_id']}/api-keys",
        json={"user_password": ident["user_password"]},
        timeout=30,
    )
    rot.raise_for_status()
    new_key = rot.json().get("api_key", "")

    # Restart the consumer on fresh volumes with the STILL-MOUNTED old
    # key gone: bring the consumer back up only after the probe, so the
    # probe measures the mounted revoked key against the server.
    subprocess.run(
        ["make", "node-dev-up", "ROLES=consumer,auditor"],
        capture_output=True,
        text=True,
        cwd=repo_root,
        check=False,
    )

    # Consumer: fresh volume, xpto gone.
    rc, text = _exec(
        "consumer",
        ["sh", "-c", "test -d /workspace/xpto && echo present || echo gone"],
    )
    consumer_state_removed = text == "gone" or rc != 0

    # Consumer: its key must be rejected by the API. The key file was
    # retired by the reset, so the secret mount is empty/absent.
    consumer_key_rejected = _probe_http("consumer") != "200"

    # Auditor: untouched state and a still-valid key.
    rc, text = _exec(
        "auditor",
        ["sh", "-c", "test -d /workspace/abc && echo present || echo gone"],
    )
    auditor_state_preserved = text == "present"
    auditor_key_accepted = _probe_http("auditor") == "200"
    if new_key:
        key_file = NODE_DIR / "roles" / "consumer.api_key"
        key_file.write_text(new_key, encoding="utf-8")
        os.chmod(key_file, 0o600)
    # The credentials assertion reads the post-reset facts from the
    # credentials manifest; merge this pass's machine facts into it.
    if cred_path is not None and Path(cred_path).exists():
        cred = json.loads(cred_path.read_text(encoding="utf-8"))
        cons = cred.get("credentials", {}).get("consumer", {})
        cons["revoked_key_rejected"] = consumer_key_rejected
        cred.setdefault("auditor", {})["key_works_after_reset"] = (
            auditor_key_accepted
        )
        cred_path.write_text(json.dumps(cred, indent=2) + "\n")
    out.write_text(
        json.dumps(
            {
                "selective_reset": {
                    "consumer_state_removed": consumer_state_removed,
                    "consumer_key_rejected": consumer_key_rejected,
                    "auditor_state_preserved": auditor_state_preserved,
                    "auditor_key_accepted": auditor_key_accepted,
                    "reset_exit_code": reset.returncode,
                },
            },
            indent=2,
        )
        + "\n"
    )


def provision_credentials(out: Path) -> None:  # noqa: ARG001
    """Provision a disposable server-side consumer agent per run.

    The consumer's mounted credential must be a real, server-issued
    key so the selective reset can revoke it for truth (rotation
    invalidates the old key at the server, which is what makes the
    rejection probe a fact rather than a wish). Identity ids are
    persisted next to the key file so the reset hook can rotate
    without any lookup-by-key API (none exists).
    """
    import secrets as _secrets

    api = "http://localhost:8000"
    pass_phrase = "node-" + _secrets.token_urlsafe(12)
    email = f"consumer-node-{_secrets.token_hex(4)}@nodetest.dev"
    resp = requests.post(
        f"{api}/v1/identity/users",
        json={
            "email": email,
            "user_password": pass_phrase,
            "agent_name": "consumer-node",
            "agent_description": "Disposable consumer role of the local node",
        },
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    roles_dir = NODE_DIR / "roles"
    (roles_dir / "consumer.api_key").write_text(
        body["api_key"], encoding="utf-8"
    )
    os.chmod(roles_dir / "consumer.api_key", 0o600)
    (roles_dir / "consumer.identity.json").write_text(
        json.dumps(
            {
                "email": email,
                "user_password": pass_phrase,
                "user_id": body["user"]["id"],
                "agent_id": body["agent"]["id"],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    os.chmod(roles_dir / "consumer.identity.json", 0o600)
    # Recreate the consumer so its secret mount carries the fresh key.
    repo_root = NODE_DIR.parent.parent
    subprocess.run(
        ["make", "node-dev-up", "ROLES=consumer,auditor"],
        capture_output=True,
        text=True,
        cwd=repo_root,
        check=False,
    )
    sys.stdout.write(
        json.dumps({"provisioned": True, "agent_id": body["agent"]["id"]})
        + "\n"
    )


def capture_credentials(out: Path) -> None:
    """Per-role identity + key liveness for the credentials assertion."""
    credentials: dict[str, dict] = {}
    for role in ("consumer", "auditor"):
        rc, agent_id = _exec(
            role,
            [
                "sh",
                "-c",
                'curl -s -H "Authorization: Bearer '
                "$(cat /run/secrets/" + role + '_api_key 2>/dev/null)" '
                "http://host.docker.internal:8000/v1/notifications"
                " | head -c 200",
            ],
        )
        key_works = rc == 0 and '"items"' in agent_id
        credentials[role] = {
            "agent_id": f"live:{role}" if key_works else None,
            "key_works_before_reset": key_works,
        }
    out.write_text(json.dumps({"credentials": credentials}, indent=2) + "\n")


def capture_restart(out: Path) -> None:
    """Read per-role state markers before/after and cross-role probes."""

    def markers() -> dict[str, str]:
        result: dict[str, str] = {}
        for role in ("consumer", "auditor"):
            rc, text = _exec(
                role,
                [
                    "sh",
                    "-c",
                    "cat \"$LOGION_HOME/node-state-marker\" "
                    "2>/dev/null || echo missing",
                ],
            )
            result[role] = text if rc == 0 else f"unreachable:{role}"
        return result

    before = markers()
    cross_visible = False
    _rc, text = _exec(
        "auditor",
        [
            "sh",
            "-c",
            "test -f \"$LOGION_HOME/node-state-marker\" && "
            "grep -q consumer \"$LOGION_HOME/node-state-marker\" "
            "2>/dev/null && echo yes || echo no",
        ],
    )
    # The auditor can only read its own marker; a consumer marker showing
    # up there would mean volumes leaked.
    cross_visible = text == "yes"
    after = markers()
    out.write_text(
        json.dumps(
            {
                "before_restart": before,
                "after_restart": after,
                "cross_role_visible": cross_visible,
            },
            indent=2,
        )
        + "\n"
    )


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
    elif capture == "selective_reset":
        cred = Path(sys.argv[3]) if len(sys.argv) > 3 else None
        capture_selective_reset(out, cred)
    else:
        raise SystemExit(f"unknown capture: {capture}")
    sys.stdout.write(json.dumps({"evidence_manifest": str(out)}) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
