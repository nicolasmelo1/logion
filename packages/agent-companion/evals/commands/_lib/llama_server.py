"""llama-server lifecycle helper.

Context manager that boots a local ``llama-server``, waits for
``/health``, yields the process, and guarantees teardown on normal
exit, exception, or SIGINT/SIGTERM.
"""

from __future__ import annotations

import atexit
import contextlib
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from evals.harness.providers.llama_cpp import (
    LlamaCppProvider,
    load_llama_cpp_provider,
)


class LlamaServerError(RuntimeError):
    """Raised when llama-server fails to boot, become healthy, or
    exit cleanly."""


def health_url_for(base_url: str) -> str:
    parts = urlsplit(base_url)
    return urlunsplit((parts.scheme, parts.netloc, "/health", "", ""))


def load_provider(config_path: Path, model_id: str) -> LlamaCppProvider:
    return load_llama_cpp_provider(config_path, model_id)


def override_ctx_size(args: Sequence[str], ctx_size: int) -> list[str]:
    """Strip any existing ``--ctx-size`` / ``-c`` pair and append a
    fresh ``--ctx-size <ctx_size>``.
    """
    out: list[str] = []
    skip_next = False
    for arg in args:
        if skip_next:
            skip_next = False
            continue
        if arg in {"--ctx-size", "-c"}:
            skip_next = True
            continue
        out.append(arg)
    out.extend(["--ctx-size", str(ctx_size)])
    return out


def ensure_model_and_alias(
    args: Sequence[str], model_path: Path, model_id: str
) -> list[str]:
    """Inject ``-m <model_path>`` and ``--alias <model_id>`` when
    either is missing from ``args``.
    """
    out = list(args)
    has_model = any(a in {"-m", "--model"} for a in out)
    has_alias = "--alias" in out
    if not has_model:
        out.extend(["-m", str(model_path)])
    if not has_alias:
        out.extend(["--alias", model_id])
    return out


def lift_fd_limit(target: int = 4096) -> None:
    """Raise the soft fd limit for long DSPy/GEPA runs (no-op on
    Windows where the ``resource`` module is unavailable)."""
    try:
        import resource

        soft, hard = resource.getrlimit(resource.RLIMIT_NOFILE)
        new = min(target, hard) if hard > 0 else target
        if new > soft:
            resource.setrlimit(resource.RLIMIT_NOFILE, (new, hard))
    except (ImportError, ValueError, OSError):
        # ImportError on Windows; ValueError/OSError if the platform
        # refuses the requested value.  Either way, continue — the
        # scripts always treated this as best-effort.
        pass


def require_command(name: str) -> str:
    """Return the absolute path to ``name`` or raise ``LlamaServerError``."""
    path = shutil.which(name)
    if not path:
        raise LlamaServerError(f"{name} not found in PATH")
    return path


def _wait_for_health(
    health_url: str, attempts: int = 60, delay: float = 1.0
) -> bool:
    for _ in range(attempts):
        try:
            with urllib.request.urlopen(health_url, timeout=2) as resp:
                if 200 <= resp.status < 300:
                    return True
        except (urllib.error.URLError, ConnectionError, TimeoutError):
            pass
        time.sleep(delay)
    return False


@contextlib.contextmanager
def llama_server_running(
    bin_path: str,
    args: Sequence[str],
    health_url: str,
    *,
    label: str = "",
) -> Iterator[subprocess.Popen[bytes]]:
    """Boot llama-server, wait for ``/health``, yield the process.

    Always terminates the process on exit (normal, exception, or
    SIGINT/SIGTERM) via ``atexit`` + signal handlers.
    """
    proc = subprocess.Popen([bin_path, *args])
    sys.stdout.write(
        f"Started {bin_path} pid={proc.pid}"
        + (f" for {label}" if label else "")
        + "\n"
    )
    sys.stdout.flush()

    def _terminate() -> None:
        if proc.poll() is not None:
            return
        with contextlib.suppress(ProcessLookupError, OSError):
            proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError, OSError):
                proc.kill()

    def _on_signal(*_args: Any) -> None:
        _terminate()
        sys.exit(130)

    atexit.register(_terminate)
    prev_handlers: dict[signal.Signals, Any] = {}
    for sig in (signal.SIGINT, signal.SIGTERM):
        prev_handlers[sig] = signal.signal(sig, _on_signal)

    try:
        if not _wait_for_health(health_url):
            raise LlamaServerError(
                f"llama-server did not become healthy at {health_url}"
            )
        yield proc
    finally:
        for sig, handler in prev_handlers.items():
            with contextlib.suppress(ValueError, OSError):
                signal.signal(sig, handler)
        _terminate()
