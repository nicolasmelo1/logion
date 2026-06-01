# SPDX-License-Identifier: MIT
"""Boot a local llama-server and run the eval harness against it."""

from __future__ import annotations

import argparse
import os
import shlex
import subprocess
import sys
from pathlib import Path

from evals.commands._lib.env import load_env_file
from evals.commands._lib.llama_server import (
    LlamaServerError,
    health_url_for,
    llama_server_running,
    load_provider,
    require_command,
)
from evals.commands._lib.paths import PACKAGE_ROOT, resolve_path


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Boot llama-server and run the eval harness.",
    )
    parser.add_argument(
        "--config",
        default=os.environ.get(
            "LOGION_LLAMACPP_CONFIG",
            "evals/harness/providers/llama_cpp_local.example.yaml",
        ),
        help="Path to the provider yaml.",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("LOGION_LLAMACPP_MODEL_ID", "qwen3-8b-q5km"),
        help="Model id from the provider yaml.",
    )
    parser.add_argument(
        "--scenarios",
        default=os.environ.get("LOGION_EVAL_SCENARIOS", "evals/scenarios"),
    )
    parser.add_argument(
        "--catalog",
        default=os.environ.get(
            "LOGION_EVAL_CATALOG", "evals/catalogs/fake-marketplace.yaml"
        ),
    )
    parser.add_argument(
        "--report",
        default=os.environ.get(
            "LOGION_EVAL_REPORT", "evals/reports/last-run.json"
        ),
    )
    parser.add_argument(
        "--llama-extra-args",
        default=os.environ.get("LLAMA_EXTRA_ARGS", ""),
        help="Extra args appended verbatim to the llama-server command.",
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=PACKAGE_ROOT / ".env",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    load_env_file(args.env_file)

    llama_bin = require_command(
        os.environ.get("LLAMA_SERVER_BIN", "llama-server")
    )
    require_command("uv")

    config_path = resolve_path(args.config, PACKAGE_ROOT)
    scenarios_path = resolve_path(args.scenarios, PACKAGE_ROOT)
    catalog_path = resolve_path(args.catalog, PACKAGE_ROOT)
    report_path = resolve_path(args.report, PACKAGE_ROOT)

    provider = load_provider(config_path, args.model)
    server_args = list(provider.model.server_args)
    if not server_args:
        raise LlamaServerError(
            f"No server_args found for model {args.model} in {config_path}"
        )

    if args.llama_extra_args:
        server_args.extend(shlex.split(args.llama_extra_args))

    health = health_url_for(provider.base_url)
    with llama_server_running(
        llama_bin, server_args, health, label=f"model={args.model}"
    ):
        subprocess.run(
            [
                "uv",
                "run",
                "python",
                "evals/run_eval.py",
                "--provider",
                "llama_cpp_local",
                "--config",
                str(config_path),
                "--model",
                args.model,
                "--scenarios",
                str(scenarios_path),
                "--catalog",
                str(catalog_path),
                "--report",
                str(report_path),
            ],
            check=True,
            cwd=PACKAGE_ROOT,
        )

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except LlamaServerError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
