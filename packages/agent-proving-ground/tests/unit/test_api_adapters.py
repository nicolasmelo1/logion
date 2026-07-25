from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Thread

import pytest

from agent_proving_ground.api_adapters._env import (
    build_devrig_env_for_agent,
    parse_export_env_file,
    validate_devrig_env,
)
from agent_proving_ground.api_adapters._http import (
    HealthCheckError,
)
from agent_proving_ground.api_adapters.local_devrig import (
    LocalDevrigAdapter,
)
from agent_proving_ground.api_adapters.remote import RemoteApiAdapter
from agent_proving_ground.config import InconclusiveRun


class _HealthHandler(BaseHTTPRequestHandler):
    def log_message(
        self,
        _format: str,
        *_args: object,
    ) -> None:
        pass

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"status": "ok"}).encode("utf-8"))


@pytest.fixture
def fake_api_server():
    server = HTTPServer(("127.0.0.1", 0), _HealthHandler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()
    server.server_close()
    thread.join(timeout=5.0)


async def test_remote_health_check_passes(fake_api_server) -> None:
    adapter = RemoteApiAdapter(base_url=fake_api_server)
    await adapter.start()
    world = await adapter.create_world("run-1", "test", ["a"])
    assert world.base_url == fake_api_server
    assert world.agent_env["a"]["LOGION_BASE_URL"] == fake_api_server


async def test_remote_missing_base_url_is_inconclusive() -> None:
    old = os.environ.pop("LOGION_PROVING_GROUND_BASE_URL", None)
    try:
        with pytest.raises(HealthCheckError, match="remote adapter requires"):
            RemoteApiAdapter()
    finally:
        if old is not None:
            os.environ["LOGION_PROVING_GROUND_BASE_URL"] = old


async def test_remote_query_returns_unsupported_for_unknown(
    fake_api_server,
    monkeypatch,
) -> None:
    for name in (
        "LOGION_PROVING_GROUND_ROLE_KEYS_FILE",
        "LOGION_PROVING_GROUND_API_KEY",
        "LOGION_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    adapter = RemoteApiAdapter(base_url=fake_api_server)
    world = await adapter.create_world("run-1", "test", ["a"])
    result = await adapter.query(world, {"type": "course_exists"})
    assert result.get("unsupported") is True


def test_parse_export_env_file_reads_quoted_values(tmp_path) -> None:
    env_file = tmp_path / "devrig.env"
    env_file.write_text(
        "# comment\n"
        'export LOGION_DEVRIG_MODE="mock"\n'
        "export LOGION_BASE_URL=http://127.0.0.1:4010\n"
        "export LOGION_API_BASE_URL=http://127.0.0.1:4010\n"
        "export LOGION_DEVRIG_ROLE=seller\n",
        encoding="utf-8",
    )
    env = parse_export_env_file(env_file)
    assert env["LOGION_DEVRIG_MODE"] == "mock"
    assert env["LOGION_BASE_URL"] == "http://127.0.0.1:4010"
    assert env["LOGION_DEVRIG_ROLE"] == "seller"


def test_validate_devrig_env_requires_mode_and_urls() -> None:
    with pytest.raises(InconclusiveRun, match="missing required keys"):
        validate_devrig_env({})
    with pytest.raises(InconclusiveRun, match="invalid LOGION_DEVRIG_MODE"):
        validate_devrig_env({
            "LOGION_DEVRIG_MODE": "staging",
            "LOGION_BASE_URL": "http://example.test",
            "LOGION_API_BASE_URL": "http://example.test",
        })


def test_build_devrig_env_for_agent_overrides_role() -> None:
    base = {
        "LOGION_DEVRIG_MODE": "mock",
        "LOGION_BASE_URL": "http://127.0.0.1:4010",
        "LOGION_API_BASE_URL": "http://127.0.0.1:4010",
        "LOGION_DEVRIG_ROLE": "seller",
    }
    env = build_devrig_env_for_agent(base, "learner", "buyer", "run-1")
    assert env["LOGION_DEVRIG_ROLE"] == "buyer"
    assert env["LOGION_PROVING_GROUND_RUN_ID"] == "run-1"
    assert env["LOGION_PROVING_GROUND_AGENT_ID"] == "learner"


async def test_local_devrig_reads_env_and_applies_role_overrides(
    tmp_path, fake_api_server
) -> None:
    devrig_dir = tmp_path / ".devrig"
    devrig_dir.mkdir()
    (devrig_dir / "devrig.env").write_text(
        f"export LOGION_DEVRIG_MODE=mock\n"
        f"export LOGION_BASE_URL={fake_api_server}\n"
        f"export LOGION_API_BASE_URL={fake_api_server}\n"
        f"export LOGION_DEVRIG_ROLE=seller\n",
        encoding="utf-8",
    )
    (tmp_path / "scripts" / "devrig.py").parent.mkdir(parents=True)
    (tmp_path / "scripts" / "devrig.py").write_text("# placeholder")

    adapter = LocalDevrigAdapter(devrig_root=tmp_path)
    await adapter.start()
    world = await adapter.create_world(
        "run-1",
        "test",
        ["creator", "learner"],
        agent_roles={"creator": "seller", "learner": "buyer"},
    )
    assert world.base_url == fake_api_server
    assert world.agent_env["creator"]["LOGION_DEVRIG_ROLE"] == "seller"
    assert world.agent_env["learner"]["LOGION_DEVRIG_ROLE"] == "buyer"


async def test_local_devrig_loads_role_specific_keys_and_homes(
    tmp_path, fake_api_server, monkeypatch
) -> None:
    for name in (
        "LOGION_PROVING_GROUND_ROLE_KEYS_FILE",
        "LOGION_PROVING_GROUND_API_KEY",
        "LOGION_API_KEY",
        "LOGION_HOME",
        "LOGION_PUBLIC_REPO_PATH",
    ):
        monkeypatch.delenv(name, raising=False)
    devrig_dir = tmp_path / ".devrig"
    devrig_dir.mkdir()
    (devrig_dir / "devrig.env").write_text(
        f"export LOGION_DEVRIG_MODE=mock\n"
        f"export LOGION_BASE_URL={fake_api_server}\n"
        f"export LOGION_API_BASE_URL={fake_api_server}\n"
        f"export LOGION_DEVRIG_ROLE=seller\n",
        encoding="utf-8",
    )
    (tmp_path / "scripts" / "devrig.py").parent.mkdir(parents=True)
    (tmp_path / "scripts" / "devrig.py").write_text("# placeholder")

    role_values = {
        "seller": "seller-value",
        "buyer": "buyer-value",
    }  # pragma: allowlist secret
    for role in ("seller", "buyer"):
        role_dir = devrig_dir / role
        (role_dir / "logion-home").mkdir(parents=True)
        (role_dir / ".api-key").write_text(
            role_values[role],
            encoding="utf-8",
        )
        (role_dir / "logion-home" / "credentials.json").write_text(
            json.dumps({
                "api_key": f"{role}-credentials-value",
                "agent_id": f"{role}-agent",
            }),
            encoding="utf-8",
        )

    adapter = LocalDevrigAdapter(devrig_root=tmp_path)
    await adapter.start()
    world = await adapter.create_world(
        "run-1",
        "test",
        ["creator", "learner"],
        agent_roles={"creator": "seller", "learner": "buyer"},
    )

    api_key_field = "LOGION_API_KEY"  # pragma: allowlist secret
    assert (
        world.agent_env["creator"][api_key_field] == "seller-credentials-value"
    )
    assert (
        world.agent_env["learner"][api_key_field] == "buyer-credentials-value"
    )
    assert world.agent_env["creator"]["LOGION_HOME"].endswith(
        "/.devrig/seller/logion-home"
    )
    assert world.agent_env["learner"]["LOGION_HOME"].endswith(
        "/.devrig/buyer/logion-home"
    )


async def test_local_devrig_missing_env_is_inconclusive(tmp_path) -> None:
    adapter = LocalDevrigAdapter(devrig_root=tmp_path)
    with pytest.raises(InconclusiveRun, match="devrig env file not found"):
        await adapter.start()


async def test_local_devrig_unhealthy_endpoint_is_inconclusive(
    tmp_path,
) -> None:
    devrig_dir = tmp_path / ".devrig"
    devrig_dir.mkdir()
    (devrig_dir / "devrig.env").write_text(
        "export LOGION_DEVRIG_MODE=mock\n"
        "export LOGION_BASE_URL=http://127.0.0.1:9\n"
        "export LOGION_API_BASE_URL=http://127.0.0.1:9\n"
        "export LOGION_DEVRIG_ROLE=seller\n",
        encoding="utf-8",
    )
    (tmp_path / "scripts" / "devrig.py").parent.mkdir(parents=True)
    (tmp_path / "scripts" / "devrig.py").write_text("# placeholder")

    adapter = LocalDevrigAdapter(devrig_root=tmp_path)
    with pytest.raises(InconclusiveRun, match="health check"):
        await adapter.start()
