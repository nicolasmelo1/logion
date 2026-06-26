# SPDX-License-Identifier: MIT
"""Handler manifest coverage + artifact emission.

Walks the argparse tree from ``build_parser()``, AST-scans each leaf's
handler module for SDK imports (``cli._context.make_client`` /
``logion.LogionClient``), and asserts every SDK-backed leaf has an entry
in ``packages/cli/handler_manifest.yaml``.

As a side effect, writes ``packages/cli/.artifacts/handler_manifest.json``
which the workspace contract-audit consumes.
"""

from __future__ import annotations

import argparse
import ast
import importlib
import json
import os
from contextlib import contextmanager
from pathlib import Path

import yaml

from cli._parser import build_parser

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = PACKAGE_ROOT / "handler_manifest.yaml"
ARTIFACT_PATH = PACKAGE_ROOT / ".artifacts" / "handler_manifest.json"

SDK_IMPORT_TARGETS = {
    ("cli._context", "make_client"),
    ("logion", "LogionClient"),
}


@contextmanager
def _admin_enabled_temporarily():
    old = os.environ.get("LOGION_ENABLE_ADMIN")
    os.environ["LOGION_ENABLE_ADMIN"] = "1"
    try:
        yield
    finally:
        if old is None:
            os.environ.pop("LOGION_ENABLE_ADMIN", None)
        else:
            os.environ["LOGION_ENABLE_ADMIN"] = old


def _leaves(parser: argparse.ArgumentParser, prefix: tuple[str, ...] = ()):
    sub = next(
        (
            a
            for a in parser._actions
            if isinstance(a, argparse._SubParsersAction)
        ),
        None,
    )
    if sub is None:
        handler = parser.get_default("handler") or parser.get_default("func")
        yield {
            "command": " ".join(prefix),
            "handler_module": getattr(handler, "__module__", None)
            if handler
            else None,
        }
        return
    for name, sub_parser in sub.choices.items():
        yield from _leaves(sub_parser, (*prefix, name))


def _imports_sdk(module_name: str | None) -> bool:
    if not module_name:
        return False
    try:
        mod = importlib.import_module(module_name)
    except Exception:
        return False
    file = getattr(mod, "__file__", None)
    if not file:
        return False
    try:
        tree = ast.parse(Path(file).read_text())
    except OSError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod_name = node.module or ""
            for alias in node.names:
                if (mod_name, alias.name) in SDK_IMPORT_TARGETS:
                    return True
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "logion":
                    return True
    return False


def test_handler_manifest_covers_every_sdk_backed_leaf():
    manifest = yaml.safe_load(MANIFEST_PATH.read_text()) or {}
    declared = set((manifest.get("commands") or {}).keys())
    with _admin_enabled_temporarily():
        sdk_backed = [
            leaf["command"]
            for leaf in _leaves(build_parser())
            if _imports_sdk(leaf["handler_module"])
        ]
    missing = sorted(set(sdk_backed) - declared)
    assert not missing, (
        "Add handler_manifest.yaml entries for these SDK-backed CLI leaves: "
        f"{missing}"
    )


def test_handler_manifest_no_stale_entries():
    """Manifest entries must correspond to real CLI leaves."""
    manifest = yaml.safe_load(MANIFEST_PATH.read_text()) or {}
    declared = set((manifest.get("commands") or {}).keys())
    with _admin_enabled_temporarily():
        real_leaves = {leaf["command"] for leaf in _leaves(build_parser())}
    stale = sorted(declared - real_leaves)
    assert not stale, (
        f"Remove handler_manifest.yaml entries for leaves that no longer "
        f"exist: {stale}"
    )


def test_handler_manifest_writes_artifact():
    """Side-effect: write the JSON artifact the workspace audit consumes."""
    manifest = yaml.safe_load(MANIFEST_PATH.read_text()) or {}
    ARTIFACT_PATH.parent.mkdir(exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True))
    assert ARTIFACT_PATH.exists()
