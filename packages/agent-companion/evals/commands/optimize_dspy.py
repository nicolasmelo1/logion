# SPDX-License-Identifier: MIT
"""Boot a local llama-server and run DSPy offline optimization.

Pick a signature with ``--target {policy,references}``:

- ``policy``     — decision-policy signature; needs a catalog and a
  scenarios split (re-uses ``split.json`` when ``--reuse-split``).
- ``references`` — reference-routing signature; no catalog, single
  scenarios YAML, in-process splitting.

The two targets share the llama-server lifecycle (boot, healthcheck,
ctx-size override, ``-m``/``--alias`` injection, cleanup); only the
optimizer entry point invoked at the end differs.
"""

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
    ensure_model_and_alias,
    health_url_for,
    lift_fd_limit,
    llama_server_running,
    load_provider,
    override_ctx_size,
    require_command,
)
from evals.commands._lib.paths import PACKAGE_ROOT, resolve_path

TARGETS = ("policy", "references")


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--target",
        choices=TARGETS,
        required=True,
        help=(
            "Which optimization to run: 'policy' (decision-policy "
            "signature) or 'references' (reference-routing signature)."
        ),
    )
    parser.add_argument(
        "--config",
        default=os.environ.get(
            "LOGION_LLAMACPP_CONFIG",
            "evals/harness/providers/llama_cpp_local.example.yaml",
        ),
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("LOGION_LLAMACPP_MODEL_ID", "qwen3-4b-q4km"),
    )
    parser.add_argument(
        "--optimizer",
        default=os.environ.get("LOGION_DSPY_OPTIMIZER", "bootstrap_few_shot"),
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=int(os.environ.get("LOGION_DSPY_SEED", "42")),
    )
    parser.add_argument(
        "--ctx-size",
        type=int,
        default=int(os.environ.get("LOGION_DSPY_CTX_SIZE", "16384")),
    )
    parser.add_argument(
        "--llama-extra-args",
        default=os.environ.get("LLAMA_EXTRA_ARGS", ""),
    )
    parser.add_argument("--env-file", type=Path, default=PACKAGE_ROOT / ".env")


def _add_policy_args(parser: argparse.ArgumentParser) -> None:
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
        "--split",
        default=os.environ.get(
            "LOGION_DSPY_SPLIT",
            "evals/optimizers/dspy/generated_candidates/split.json",
        ),
    )
    parser.add_argument(
        "--output",
        default=os.environ.get("LOGION_DSPY_OUTPUT", ""),
        help=(
            "Candidate report path (default: "
            "generated_candidates/candidate-<model>-<optimizer>.json)."
        ),
    )
    parser.add_argument(
        "--reuse-split",
        action="store_true",
        default=os.environ.get("LOGION_DSPY_REUSE_SPLIT") == "1",
    )


def _add_references_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--scenarios",
        default=os.environ.get(
            "LOGION_REF_ROUTING_SCENARIOS",
            "evals/scenarios/reference_routing/scenarios.yaml",
        ),
    )
    parser.add_argument(
        "--output",
        default=os.environ.get("LOGION_DSPY_REF_OUTPUT", ""),
        help=(
            "Candidate report path (default: "
            "generated_candidates/ref-candidate-<model>-<optimizer>.json)."
        ),
    )


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    """Two-pass parse: read ``--target`` first, then build the parser
    with target-specific args.  This keeps a single set of flag names
    (``--scenarios``, ``--output``) instead of disambiguating with
    ugly target-prefixed names.
    """
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--target", choices=TARGETS)
    pre_args, _ = pre.parse_known_args(argv)

    parser = argparse.ArgumentParser(
        description=(
            "Boot llama-server and run DSPy offline optimization for "
            "either the decision-policy or reference-routing signature."
        ),
    )
    _add_common_args(parser)
    if pre_args.target == "references":
        _add_references_args(parser)
    else:
        # Default and explicit 'policy' both land here so ``--help``
        # without ``--target`` shows the more common decision-policy
        # surface.
        _add_policy_args(parser)
    return parser.parse_args(argv)


def _default_output(target: str, model: str, optimizer: str) -> Path:
    prefix = "candidate" if target == "policy" else "ref-candidate"
    return (
        PACKAGE_ROOT
        / "evals/optimizers/dspy/generated_candidates"
        / f"{prefix}-{model}-{optimizer}.json"
    )


def _dspy_env(model_id: str, base_url: str) -> dict[str, str]:
    """Env vars optimize_policy.py / optimize_references.py expect."""
    dspy_key = os.environ.get("DSPY_API_KEY", "sk-local")
    return {
        **os.environ,
        "DSPY_LM": f"openai/{model_id}",
        "DSPY_API_BASE": base_url,
        "DSPY_API_KEY": dspy_key,
        "DSPY_REFLECTION_LM": os.environ.get(
            "DSPY_REFLECTION_LM", f"openai/{model_id}"
        ),
        "DSPY_REFLECTION_API_BASE": os.environ.get(
            "DSPY_REFLECTION_API_BASE", base_url
        ),
        "DSPY_REFLECTION_API_KEY": os.environ.get(
            "DSPY_REFLECTION_API_KEY", dspy_key
        ),
    }


def _resolve_model_file(provider) -> Path:
    cache_dir = Path(
        os.environ.get("MODEL_CACHE_DIR")
        or os.environ.get("LOGION_MODEL_CACHE_DIR")
        or ".models"
    )
    repo_dir = Path(provider.model.repo).name
    rel = cache_dir / repo_dir / provider.model.file
    resolved = resolve_path(rel, PACKAGE_ROOT)
    if not resolved.is_file():
        raise LlamaServerError(
            f"Model file not found: {resolved}\n"
            "Run 'make download-models' first."
        )
    return resolved


def _build_server_args(
    provider,
    model_id: str,
    ctx_size: int,
    extra_args: str,
) -> list[str]:
    args = list(provider.model.server_args)
    if not args:
        raise LlamaServerError("No server_args found in provider config")
    model_path = _resolve_model_file(provider)
    args = override_ctx_size(args, ctx_size)
    args = ensure_model_and_alias(args, model_path, model_id)
    if extra_args:
        args.extend(shlex.split(extra_args))
    return args


def _run_policy(args: argparse.Namespace, base_url: str) -> None:
    scenarios = resolve_path(args.scenarios, PACKAGE_ROOT)
    catalog = resolve_path(args.catalog, PACKAGE_ROOT)
    split = resolve_path(args.split, PACKAGE_ROOT)
    output_default = args.output or _default_output(
        "policy", args.model, args.optimizer
    )
    output = resolve_path(output_default, PACKAGE_ROOT)
    split.parent.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)

    if args.reuse_split and split.is_file():
        print(f"Reusing existing split: {split}")
    else:
        subprocess.run(
            [
                "uv",
                "run",
                "--group",
                "dspy",
                "python",
                "evals/optimizers/dspy/split_scenarios.py",
                "--scenarios",
                str(scenarios),
                "--seed",
                str(args.seed),
                "--output",
                str(split),
            ],
            check=True,
            cwd=PACKAGE_ROOT,
        )

    subprocess.run(
        [
            "uv",
            "run",
            "--group",
            "dspy",
            "python",
            "evals/optimizers/dspy/optimize_policy.py",
            "--scenarios",
            str(scenarios),
            "--catalog",
            str(catalog),
            "--optimizer",
            args.optimizer,
            "--seed",
            str(args.seed),
            "--split",
            str(split),
            "--output",
            str(output),
        ],
        check=True,
        env=_dspy_env(args.model, base_url),
        cwd=PACKAGE_ROOT,
    )
    print(f"candidate report: {output}")


def _run_references(args: argparse.Namespace, base_url: str) -> None:
    scenarios = resolve_path(args.scenarios, PACKAGE_ROOT)
    if not scenarios.is_file():
        raise LlamaServerError(f"Scenarios file not found: {scenarios}")
    output_default = args.output or _default_output(
        "references", args.model, args.optimizer
    )
    output = resolve_path(output_default, PACKAGE_ROOT)
    output.parent.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        [
            "uv",
            "run",
            "--group",
            "dspy",
            "python",
            "evals/optimizers/dspy/optimize_references.py",
            "--scenarios",
            str(scenarios),
            "--optimizer",
            args.optimizer,
            "--seed",
            str(args.seed),
            "--output",
            str(output),
        ],
        check=True,
        env=_dspy_env(args.model, base_url),
        cwd=PACKAGE_ROOT,
    )
    print(f"candidate report: {output}")


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    load_env_file(args.env_file)
    lift_fd_limit()

    llama_bin = require_command(
        os.environ.get("LLAMA_SERVER_BIN", "llama-server")
    )
    require_command("uv")

    config_path = resolve_path(args.config, PACKAGE_ROOT)
    provider = load_provider(config_path, args.model)
    server_args = _build_server_args(
        provider, args.model, args.ctx_size, args.llama_extra_args
    )
    base_url = provider.base_url
    health = health_url_for(base_url)

    signature = (
        "decision_policy" if args.target == "policy" else "reference_routing"
    )
    label = f"model={args.model} signature={signature}"
    print(f"DSPy will target {base_url} via openai/{args.model} ({label})")

    with llama_server_running(llama_bin, server_args, health, label=label):
        if args.target == "policy":
            _run_policy(args, base_url)
        else:
            _run_references(args, base_url)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except LlamaServerError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
