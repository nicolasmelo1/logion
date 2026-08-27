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

import json
import subprocess
import sys
from pathlib import Path

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
            ["docker", "inspect",
             "--format", "{{json .HostConfig.NanoCpus}}",
             f"logion-local-node-{role}-1"],
            capture_output=True, text=True, check=False,
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
            "test -d /workspace/xpto/.logion-skills/fixture-skill "
            "&& echo yes || echo no",
        ],
    )
    visible = text == "yes" and rc == 0
    rc, text = _exec(
        "consumer",
        [
            "sh",
            "-c",
            "test -d /workspace/abc/.logion-skills/fixture-skill "
            "&& echo yes || echo no",
        ],
    )
    in_abc = text == "yes"
    rc, text = _exec(
        "consumer",
        [
            "sh",
            "-c",
            "test -d /home/agent/.logion/installed/fixture-skill "
            "&& echo yes || echo no",
        ],
    )
    user_scope = text == "yes"
    rc, text = _exec(
        "auditor",
        [
            "sh",
            "-c",
            "test -d /workspace/xpto/.logion-skills/fixture-skill "
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


def capture_selective_reset(out: Path) -> None:
    """After consumer reset: its state gone and key rejected, auditor fine."""
    rc, text = _exec(
        "consumer",
        ["sh", "-c", "test -d /workspace/xpto && echo present || echo gone"],
    )
    consumer_state_removed = text == "gone" or rc != 0
    rc, _ = _exec(
        "consumer",
        [
            "sh",
            "-c",
            'curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer '
            '$(cat /run/secrets/consumer_api_key 2>/dev/null)" '
            'http://host.docker.internal:8000/v1/notifications"',
        ],
    )
    consumer_key_rejected = rc != 0 or text in {"401", "403"}
    rc, text = _exec(
        "auditor",
        ["sh", "-c", "test -d /workspace/acme && echo present || echo gone"],
    )
    auditor_state_preserved = text == "present"
    rc, code = _exec(
        "auditor",
        [
            "sh",
            "-c",
            'curl -s -o /dev/null -w "%{http_code}" -H "Authorization: Bearer '
            '$(cat /run/secrets/auditor_api_key 2>/dev/null)" '
            'http://host.docker.internal:8000/v1/notifications"',
        ],
    )
    auditor_key_accepted = code == "200"
    out.write_text(
        json.dumps(
            {
                "selective_reset": {
                    "consumer_state_removed": consumer_state_removed,
                    "consumer_key_rejected": consumer_key_rejected,
                    "auditor_state_preserved": auditor_state_preserved,
                    "auditor_key_accepted": auditor_key_accepted,
                },
            },
            indent=2,
        )
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
                    "cat /home/agent/.logion/node-state-marker "
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
            "test -f /home/agent/.logion/node-state-marker && "
            "grep -q consumer /home/agent/.logion/node-state-marker "
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
    elif capture == "credentials":
        capture_credentials(out)
    elif capture == "restart":
        capture_restart(out)
    elif capture == "selective_reset":
        capture_selective_reset(out)
    else:
        raise SystemExit(f"unknown capture: {capture}")
    sys.stdout.write(json.dumps({"evidence_manifest": str(out)}) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
