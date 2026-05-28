"""Development eval command wrappers for Logion companion experiments."""

from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType

_DSPY_OPTIMIZERS = ("bootstrap_few_shot", "mipro_v2")


def register(subparsers: argparse._SubParsersAction) -> None:
    """Register the ``evals`` development command group."""
    parser = subparsers.add_parser(
        "evals",
        help="Run Logion evaluation and optimizer development workflows",
    )
    sub = parser.add_subparsers(dest="evals_command", required=True)

    dspy = sub.add_parser(
        "dspy",
        help="Run DSPy offline optimization workflows",
    )
    dspy_sub = dspy.add_subparsers(dest="dspy_command", required=True)

    split = dspy_sub.add_parser(
        "split-scenarios",
        help="Split eval scenarios into train/dev/test JSON",
    )
    split.add_argument(
        "--scenarios",
        type=Path,
        default=Path("evals/scenarios"),
        help="Directory containing scenario YAML files.",
    )
    split.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Hash seed for deterministic splitting.",
    )
    split.add_argument(
        "--ratios",
        default="0.6,0.2,0.2",
        help="Comma-separated train,dev,test ratios (must sum to 1).",
    )
    split.add_argument(
        "--output",
        type=Path,
        default=Path("evals/optimizers/dspy/generated_candidates/split.json"),
        help="Path to write the split JSON.",
    )
    split.set_defaults(handler=handle_dspy_split)

    optimize = dspy_sub.add_parser(
        "optimize-policy",
        help="Run DSPy optimization for the companion decision policy",
    )
    optimize.add_argument(
        "--scenarios",
        type=Path,
        default=Path("evals/scenarios"),
        help="Directory containing scenario YAML files.",
    )
    optimize.add_argument(
        "--catalog",
        type=Path,
        default=Path("evals/catalogs/fake-marketplace.yaml"),
        help="Path to the catalog YAML.",
    )
    optimize.add_argument(
        "--optimizer",
        default="bootstrap_few_shot",
        choices=_DSPY_OPTIMIZERS,
        help="DSPy optimizer to use.",
    )
    optimize.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Seed for scenario splitting (ignored if --split is given).",
    )
    optimize.add_argument(
        "--split",
        type=Path,
        dest="split_path",
        help="Path to a split JSON from split-scenarios.",
    )
    optimize.add_argument(
        "--output",
        type=Path,
        help="Path to write the candidate report JSON.",
    )
    optimize.set_defaults(handler=handle_dspy_optimize)


def handle_dspy_split(args: argparse.Namespace) -> int:
    """Delegate to the DSPy split-scenarios script."""
    return _run_dspy_script(
        "split_scenarios.py",
        [
            "--scenarios",
            str(args.scenarios),
            "--seed",
            str(args.seed),
            "--ratios",
            args.ratios,
            "--output",
            str(args.output),
        ],
    )


def handle_dspy_optimize(args: argparse.Namespace) -> int:
    """Delegate to the DSPy optimize-policy script."""
    script_args = [
        "--scenarios",
        str(args.scenarios),
        "--catalog",
        str(args.catalog),
        "--optimizer",
        args.optimizer,
        "--seed",
        str(args.seed),
    ]
    if args.split_path is not None:
        script_args.extend(["--split", str(args.split_path)])
    if args.output is not None:
        script_args.extend(["--output", str(args.output)])
    return _run_dspy_script("optimize_policy.py", script_args)


def _run_dspy_script(script_name: str, args: list[str]) -> int:
    """Run a DSPy optimizer script with the current Python interpreter."""
    script = _dspy_script_path(script_name)
    if script is None:
        sys.stderr.write(
            "error: could not locate agent-companion DSPy optimizer scripts; "
            "run from the repo workspace or set LOGION_AGENT_COMPANION_ROOT\n"
        )
        return 2

    try:
        module = _load_script_module(script)
    except ModuleNotFoundError as exc:
        if exc.name != "dspy":
            raise
        sys.stderr.write(
            "error: DSPy is not installed; rerun with "
            "`uv run --group dspy logion evals dspy ...`\n"
        )
        return 2
    previous_argv = sys.argv[:]
    try:
        sys.argv = [str(script), *args]
        return int(module.main())
    finally:
        sys.argv = previous_argv


def _load_script_module(script: Path) -> ModuleType:
    """Load a script file as a Python module without importing DSPy eagerly."""
    module_name = f"_logion_dspy_{script.stem}"
    spec = importlib.util.spec_from_file_location(module_name, script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load script module: {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _dspy_script_path(script_name: str) -> Path | None:
    """Resolve a DSPy optimizer script in workspace or package context."""
    env_root = os.environ.get("LOGION_AGENT_COMPANION_ROOT")
    candidates = []
    if env_root:
        candidates.append(Path(env_root))
    candidates.append(Path.cwd())
    candidates.append(Path(__file__).resolve().parents[3] / "agent-companion")

    relative = Path("evals/optimizers/dspy") / script_name
    for root in candidates:
        script = root / relative
        if script.is_file():
            return script
    return None
