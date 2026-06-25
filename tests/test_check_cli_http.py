# SPDX-License-Identifier: MIT
"""Tests for scripts/check_cli_http.py."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SCRIPT = os.path.join(REPO_ROOT, "scripts", "check_cli_http.py")


def test_real_repo_is_clean() -> None:
    result = subprocess.run(
        [sys.executable, SCRIPT],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    assert result.returncode == 0, result.stdout


def _setup_fake(tmp_path, source: str, lockfile: str = ""):  # type: ignore[no-untyped-def]
    fake = tmp_path / "fake"
    (fake / "scripts").mkdir(parents=True)
    (fake / "packages" / "cli" / "cli").mkdir(parents=True)
    shutil.copy(SCRIPT, fake / "scripts" / "check_cli_http.py")
    (fake / "scripts" / "check_cli_http.lock").write_text(lockfile)
    (fake / "packages" / "cli" / "cli" / "bad.py").write_text(source)
    return fake


def _run(fake) -> subprocess.CompletedProcess[str]:  # type: ignore[no-untyped-def]
    return subprocess.run(
        [sys.executable, str(fake / "scripts" / "check_cli_http.py")],
        capture_output=True,
        text=True,
        cwd=fake,
    )


# ── API-endpoint calls must always be flagged (route through the SDK) ──

API_CALL = (
    "import httpx\n"
    "def go(config):\n"
    '    url = f"{config.base_url}/v1/course-reviews/x/bundle"\n'
    "    return httpx.get(url)\n"
)


def test_api_endpoint_call_flagged(tmp_path) -> None:  # type: ignore[no-untyped-def]
    result = _run(_setup_fake(tmp_path, API_CALL))
    assert result.returncode == 1
    assert "bad.py" in result.stdout
    assert "/v1/" in result.stdout
    assert "SDK" in result.stdout


def test_api_endpoint_not_silenced_by_presigned_entry(  # type: ignore[no-untyped-def]
    tmp_path,
) -> None:
    """A literal /v1 URL is not 'dynamic', so a presigned-url entry
    must not cover it."""
    result = _run(
        _setup_fake(
            tmp_path,
            API_CALL,
            lockfile="packages/cli/cli/bad.py :: presigned-url :: x\n",
        )
    )
    assert result.returncode == 1


# ── presigned / dynamic URLs need a lockfile entry ──

PRESIGNED_CALL = (
    "import httpx\n"
    "def put_one(upload):\n"
    '    url = upload.get("put_url")\n'
    "    with httpx.Client() as http:\n"
    '        return http.request("PUT", url)\n'
)


def test_presigned_call_without_lockfile_flagged(tmp_path) -> None:  # type: ignore[no-untyped-def]
    result = _run(_setup_fake(tmp_path, PRESIGNED_CALL))
    assert result.returncode == 1
    assert "<dynamic url>" in result.stdout


def test_presigned_call_with_lockfile_ok(tmp_path) -> None:  # type: ignore[no-untyped-def]
    result = _run(
        _setup_fake(
            tmp_path,
            PRESIGNED_CALL,
            lockfile=(
                "packages/cli/cli/bad.py :: presigned-url :: external\n"
            ),
        )
    )
    assert result.returncode == 0, result.stdout


def test_client_stream_recognized_via_annotation(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A param annotated httpx.Client makes .stream(...) an httpx call."""
    source = (
        "import httpx\n"
        "def dl(http: httpx.Client, f):\n"
        '    return http.stream("GET", f.download_url)\n'
    )
    result = _run(_setup_fake(tmp_path, source))
    assert result.returncode == 1
    assert "<dynamic url>" in result.stdout


# ── lockfile hygiene ──


def test_stale_lockfile_entry_flagged(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """An entry that matches no call must fail (keep the lockfile tidy)."""
    result = _run(
        _setup_fake(
            tmp_path,
            "x = 1\n",  # no httpx at all
            lockfile="packages/cli/cli/bad.py :: presigned-url :: stale\n",
        )
    )
    assert result.returncode == 1
    assert "stale" in result.stdout.lower()


def test_non_httpx_dict_get_not_flagged(tmp_path) -> None:  # type: ignore[no-untyped-def]
    """A plain dict .get(...) must not be mistaken for an httpx call."""
    source = 'import httpx  # noqa\ndef go(d):\n    return d.get("key")\n'
    result = _run(_setup_fake(tmp_path, source))
    assert result.returncode == 0, result.stdout
