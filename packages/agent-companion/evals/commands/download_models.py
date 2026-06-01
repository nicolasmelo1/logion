# SPDX-License-Identifier: MIT
"""Download the local GGUF models the eval harness can run against.

Reads ``.env`` for download defaults (which models to fetch, repo /
file overrides, optional ``HF_TOKEN``).  GGUFs land under
``$LOGION_MODEL_CACHE_DIR`` (default: ``./.models``).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from evals.commands._lib.env import load_env_file
from evals.commands._lib.paths import PACKAGE_ROOT


def _hf_download(
    repo: str, file: str, target_dir: Path, hf_token: str
) -> None:
    target_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["hf", "download", repo, file, "--local-dir", str(target_dir)]
    if hf_token:
        cmd.extend(["--token", hf_token])
    print(f"==> Downloading {repo} :: {file}")
    subprocess.run(cmd, check=True)


def _selected_models() -> list[tuple[str, str, str, str]]:
    """Return ``(env_flag, repo, file, subdir)`` for each model the
    user enabled via ``LOGION_DOWNLOAD_*`` env flags.
    """
    specs = [
        (
            "LOGION_DOWNLOAD_QWEN3_4B",
            "QWEN3_4B_REPO",
            "Qwen/Qwen3-4B-GGUF",
            "QWEN3_4B_FILE",
            "Qwen3-4B-Q4_K_M.gguf",
            "Qwen3-4B-GGUF",
        ),
        (
            "LOGION_DOWNLOAD_QWEN3_8B",
            "QWEN3_8B_REPO",
            "Qwen/Qwen3-8B-GGUF",
            "QWEN3_8B_FILE",
            "Qwen3-8B-Q4_K_M.gguf",
            "Qwen3-8B-GGUF",
        ),
        (
            "LOGION_DOWNLOAD_GEMMA3_4B",
            "GEMMA3_4B_REPO",
            "unsloth/gemma-3-4b-it-GGUF",
            "GEMMA3_4B_FILE",
            "gemma-3-4b-it-Q4_K_M.gguf",
            "gemma-3-4b-it-GGUF",
        ),
    ]
    out: list[tuple[str, str, str, str]] = []
    for flag, repo_var, repo_default, file_var, file_default, subdir in specs:
        if os.environ.get(flag, "1") != "1":
            continue
        repo = os.environ.get(repo_var) or repo_default
        file_name = os.environ.get(file_var) or file_default
        out.append((flag, repo, file_name, subdir))
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Download local GGUF models for the eval harness."
    )
    parser.add_argument(
        "--env-file",
        type=Path,
        default=PACKAGE_ROOT / ".env",
        help="Path to a .env file with download defaults (default: ./.env).",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help=(
            "Where to write the GGUF files "
            "(default: $LOGION_MODEL_CACHE_DIR or ./.models)."
        ),
    )
    args = parser.parse_args(argv)

    load_env_file(args.env_file)

    if not shutil.which("hf"):
        print(
            "hf CLI not found. Install huggingface_hub CLI first.",
            file=sys.stderr,
        )
        return 1

    cache_dir_default = (
        os.environ.get("LOGION_MODEL_CACHE_DIR") or PACKAGE_ROOT / ".models"
    )
    cache_dir = (
        (args.cache_dir or Path(cache_dir_default)).expanduser().resolve()
    )
    cache_dir.mkdir(parents=True, exist_ok=True)

    hf_token = os.environ.get("HF_TOKEN", "")
    for _flag, repo, file_name, subdir in _selected_models():
        _hf_download(repo, file_name, cache_dir / subdir, hf_token)

    print(f"Downloads complete under {cache_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
