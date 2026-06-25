#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Forbid raw httpx calls in the CLI unless allowlisted in the lockfile.

The CLI must reach the logion API exclusively through the typed SDK
(``client.v1.<resource>.<op>``). Hand-rolled ``httpx`` calls bypass the
SDK's auth, retries, error handling and contract typing, and they drift
from the OpenAPI contract — exactly the kind of call this guardrail
exists to prevent.

A narrow escape hatch remains for URLs the SDK legitimately can't own:
short-lived **presigned object-storage URLs** returned inside API
payloads (e.g. ``put_url`` / ``download_url``), which point at external
storage, not the logion API. Each such call site must be declared in
``scripts/check_cli_http.lock``.

Lockfile format — one entry per line, ``#`` starts a comment::

    <repo-relative-path> :: <target> :: <reason>

``<target>`` is either:

  - ``presigned-url`` — the call's URL is dynamic (taken from an API
    payload), i.e. an external presigned URL with no SDK wrapper; or
  - a literal substring of the call's URL (a domain or path), used to
    permit a specific external endpoint.

The check FAILS when:

  - a CLI ``httpx`` network call has no matching lockfile entry (the
    common case: route it through the SDK instead); or
  - a lockfile entry matches no call (stale — delete it).

Detection is a static, best-effort AST analysis: it flags calls to
``httpx.<method>(...)`` and to objects bound to ``httpx.Client`` /
``httpx.AsyncClient`` (via assignment, ``with`` binding, or a parameter
annotation). It is deliberately conservative — when in doubt, add a
lockfile entry with a justification or move the call to the SDK.
"""

from __future__ import annotations

import ast
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LOCKFILE_PATH = os.path.join(ROOT, "scripts", "check_cli_http.lock")

# Only the CLI source is in scope — the CLI is the surface that must go
# through the SDK. Other packages (and the SDK itself) are out of scope.
CLI_SRC = os.path.join("packages", "cli", "cli")

SKIP_DIRS = {
    ".git",
    ".venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
}

# httpx methods that perform network I/O. ``Client`` / ``AsyncClient``
# (construction) are intentionally absent — only the actual requests
# matter.
NET_METHODS = {
    "get",
    "post",
    "put",
    "patch",
    "delete",
    "head",
    "options",
    "request",
    "stream",
    "send",
}

# Methods whose URL argument is the *second* positional (the first is the
# HTTP verb): ``request(method, url, ...)`` / ``stream(method, url, ...)``.
VERB_FIRST_METHODS = {"request", "stream"}

DYNAMIC = "\x00dynamic"  # sentinel: URL not statically resolvable
PRESIGNED = "presigned-url"


def load_lockfile() -> dict[tuple[str, str], bool]:
    """Return ``{(path, target): used}`` — ``used`` starts False."""
    entries: dict[tuple[str, str], bool] = {}
    if not os.path.isfile(LOCKFILE_PATH):
        return entries
    with open(LOCKFILE_PATH) as fh:
        for raw in fh:
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split("::")]
            if len(parts) >= 2 and parts[0] and parts[1]:
                entries[(parts[0], parts[1])] = False
    return entries


def _dotted(node: ast.AST) -> str | None:
    """Best-effort dotted name for ``a.b.c`` / ``a``."""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


def _annotation_is_httpx_client(node: ast.AST | None) -> bool:
    dotted = _dotted(node) if node is not None else None
    if dotted is None:
        return False
    return dotted in {
        "httpx.Client",
        "httpx.AsyncClient",
        "Client",
        "AsyncClient",
    }


def _is_httpx_client_call(node: ast.AST) -> bool:
    """True for ``httpx.Client(...)`` / ``httpx.AsyncClient(...)``."""
    if not isinstance(node, ast.Call):
        return False
    return _dotted(node.func) in {"httpx.Client", "httpx.AsyncClient"}


def _collect_httpx_handles(tree: ast.AST) -> set[str]:
    """Names bound to an httpx client within the file.

    Covers parameter annotations, plain assignments and ``with`` bindings
    so ``http.get(...)`` / ``client.stream(...)`` are recognised as httpx
    calls and not confused with, say, ``dict.get(...)``.
    """
    handles: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            a = node.args
            params = [
                *a.posonlyargs,
                *a.args,
                *a.kwonlyargs,
                *([a.vararg] if a.vararg else []),
                *([a.kwarg] if a.kwarg else []),
            ]
            for arg in params:
                if _annotation_is_httpx_client(arg.annotation):
                    handles.add(arg.arg)
        elif isinstance(node, ast.Assign) and _is_httpx_client_call(
            node.value
        ):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    handles.add(tgt.id)
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                if _is_httpx_client_call(item.context_expr) and isinstance(
                    item.optional_vars, ast.Name
                ):
                    handles.add(item.optional_vars.id)
    return handles


def _collect_str_assignments(tree: ast.AST) -> dict[str, str]:
    """Map ``name -> reconstructed URL`` for string/f-string assignments."""
    out: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            tgt = node.targets[0]
            if isinstance(tgt, ast.Name):
                hint = _url_from_node(node.value, {})
                if hint not in (None, DYNAMIC):
                    out[tgt.id] = hint  # type: ignore[assignment]
    return out


def _url_from_node(
    node: ast.AST | None, str_assignments: dict[str, str]
) -> str | None:
    """Reconstruct a URL string from *node*, or ``DYNAMIC`` if opaque."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):  # f-string
        parts: list[str] = []
        for value in node.values:
            if isinstance(value, ast.Constant) and isinstance(
                value.value, str
            ):
                parts.append(value.value)
            elif isinstance(value, ast.FormattedValue):
                parts.append("{" + (_dotted(value.value) or "?") + "}")
        return "".join(parts)
    if isinstance(node, ast.Name) and node.id in str_assignments:
        return str_assignments[node.id]
    return DYNAMIC


def _url_arg(call: ast.Call, method: str) -> ast.AST | None:
    for kw in call.keywords:
        if kw.arg == "url":
            return kw.value
    idx = 1 if method in VERB_FIRST_METHODS else 0
    if len(call.args) > idx:
        return call.args[idx]
    return None


def _is_httpx_call(call: ast.Call, handles: set[str]) -> str | None:
    """Return the network method name if *call* is an httpx request."""
    func = call.func
    if not isinstance(func, ast.Attribute) or func.attr not in NET_METHODS:
        return None
    recv = func.value
    if isinstance(recv, ast.Name) and (
        recv.id == "httpx" or recv.id in handles
    ):
        return func.attr
    return None


def scan(path: str) -> list[tuple[int, str]]:
    """Return ``(lineno, url_hint)`` for each httpx network call."""
    with open(path) as fh:
        source = fh.read()
    if "httpx" not in source:
        return []
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError:
        return []
    handles = _collect_httpx_handles(tree)
    str_assignments = _collect_str_assignments(tree)
    hits: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        method = _is_httpx_call(node, handles)
        if method is None:
            continue
        hint = _url_from_node(_url_arg(node, method), str_assignments)
        hits.append((node.lineno, hint if hint is not None else DYNAMIC))
    return hits


def iter_files() -> list[str]:
    base = os.path.join(ROOT, CLI_SRC)
    if not os.path.isdir(base):
        return []
    files: list[str] = []
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fname in filenames:
            if fname.endswith(".py"):
                files.append(os.path.join(dirpath, fname))
    return sorted(files)


def _match(rel: str, hint: str, lockfile: dict[tuple[str, str], bool]) -> bool:
    """True if a lockfile entry covers this call (and mark it used)."""
    matched = False
    for entry_path, target in lockfile:
        if entry_path != rel:
            continue
        if target == PRESIGNED:
            ok = hint == DYNAMIC
        else:
            ok = hint != DYNAMIC and target in hint
        if ok:
            lockfile[(entry_path, target)] = True
            matched = True
    return matched


def main() -> None:
    lockfile = load_lockfile()
    failures: list[tuple[str, int, str]] = []
    for path in iter_files():
        rel = os.path.relpath(path, ROOT)
        for lineno, hint in scan(path):
            if not _match(rel, hint, lockfile):
                failures.append((rel, lineno, hint))

    stale = [key for key, used in lockfile.items() if not used]

    if not failures and not stale:
        print("check_cli_http: ok.")
        return

    if failures:
        print("check_cli_http: un-allowlisted raw httpx calls in the CLI:")
        for rel, lineno, hint in failures:
            shown = "<dynamic url>" if hint == DYNAMIC else hint
            api = (
                "  ← logion API endpoint; call it via the SDK"
                if hint != DYNAMIC and ("/v1/" in hint or "base_url" in hint)
                else ""
            )
            print(f"  {rel}:{lineno}  url={shown}{api}")
        print(
            "\nRoute logion API calls through the typed SDK "
            "(client.v1.<resource>.<op>). For external/presigned URLs "
            "with no SDK wrapper, add an entry to "
            "scripts/check_cli_http.lock:\n"
            "  <path> :: presigned-url :: <reason>\n"
            "or, to permit a specific external endpoint:\n"
            "  <path> :: <domain-or-path-substring> :: <reason>"
        )
    if stale:
        print("\ncheck_cli_http: stale lockfile entries (no matching call):")
        for entry_path, target in stale:
            print(f"  {entry_path} :: {target}")
        print("Remove them from scripts/check_cli_http.lock.")
    sys.exit(1)


if __name__ == "__main__":
    main()
