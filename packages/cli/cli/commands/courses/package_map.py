# SPDX-License-Identifier: MIT
"""``logion courses package-map`` — CLI-local validate + init.

Both commands are CLI-local and never touch the network: ``validate``
checks an existing ``logion-package-map.yaml`` with the shared
``logion_skillmap`` validator, and ``init`` infers one from a local
directory walk via ``logion_skillmap.infer``.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from cli import _package_map as pmap
from cli._errors import emit_error_json, print_err
from cli._options import COMMON_PARSER
from cli._output import emit_json

_VALIDATE_KIND = "logion.courses.package-map.validate"
_INIT_KIND = "logion.courses.package-map.init"


def _result_payload(result: pmap.InferenceResult) -> dict:
    return {
        "package_map": pmap.package_map_to_dict(result.package_map),
        "source": result.source,
        "components": [
            {
                "name": c.name,
                "root": c.root,
                "entrypoint": c.entrypoint,
                "summary": c.summary,
                "content_sha256": c.content_sha256,
                "mirrors": list(c.mirrors),
            }
            for c in result.components
        ],
        "needs_review": [
            {"code": f.code, "path": f.path, "message": f.message}
            for f in result.needs_review
        ],
    }


def handle_validate(args: argparse.Namespace) -> int:
    """Validate an existing ``logion-package-map.yaml`` locally."""
    json_output = getattr(args, "json_output", False)
    root = Path(getattr(args, "dir", "."))
    path = root / pmap.PACKAGE_MAP_FILENAME
    if not path.is_file():
        msg = f"no {pmap.PACKAGE_MAP_FILENAME} found in {str(root)!r}"
        if json_output:
            emit_error_json("map_not_found", msg, 1)
        else:
            print_err(msg)
        return 1

    text = path.read_text(encoding="utf-8")
    try:
        pm = pmap.parse_package_map(text)
    except (TypeError, ValueError) as exc:
        if json_output:
            emit_error_json("package_map_invalid", str(exc), 1)
        else:
            print_err(str(exc))
        return 1

    raw = yaml.safe_load(text)
    raw = raw if isinstance(raw, dict) else {}
    warnings = pmap.check_unknown_keys_raw(raw) + pmap.validate_package_map(pm)

    if json_output:
        emit_json(
            _VALIDATE_KIND,
            {
                "valid": not warnings,
                "warnings": [
                    {"code": w.code, "path": w.path, "message": w.message}
                    for w in warnings
                ],
            },
        )
    elif not warnings:
        print(f"{path}: valid")
    else:
        print(f"{path}: {len(warnings)} warning(s)")
        for w in warnings:
            print(f"  [{w.code}] {w.path}: {w.message}")

    return 0 if not warnings else 1


def handle_init(args: argparse.Namespace) -> int:
    """Infer a package map from a local tree and write it (or emit JSON)."""
    json_output = getattr(args, "json_output", False)
    root = Path(getattr(args, "dir", "."))
    out_path = root / pmap.PACKAGE_MAP_FILENAME

    if out_path.is_file():
        msg = (
            f"{pmap.PACKAGE_MAP_FILENAME} already exists in {str(root)!r}; "
            "refusing to overwrite (author map wins)"
        )
        if json_output:
            emit_error_json("map_already_exists", msg, 1)
        else:
            print_err(msg)
        return 1

    tree, read_blob = pmap.walk_local_tree(root)
    result = pmap.infer(tree, read_blob, slug=getattr(args, "slug", None))

    # --json is the agent surface: emit the full result and never write.
    if json_output:
        emit_json(_INIT_KIND, _result_payload(result))
        return 0

    flags = result.needs_review
    if flags and not getattr(args, "yes", False):
        print(f"{len(flags)} item(s) need review before writing the map:")
        for f in flags:
            loc = f.path or "<repo>"
            print(f"  [{f.code}] {loc}: {f.message}")
        print_err(
            "re-run with --yes to accept the deterministic defaults, "
            "or address the items above"
        )
        return 2

    out_path.write_text(
        pmap.dump_package_map(result.package_map), encoding="utf-8"
    )
    print(
        f"wrote {out_path} "
        f"({len(result.components)} component(s), source={result.source})"
    )
    return 0


def register_package_map(sub: argparse._SubParsersAction) -> None:
    """Register the ``courses package-map`` subgroup."""
    parser = sub.add_parser(
        "package-map",
        help="Validate or scaffold a logion-package-map.yaml (local)",
    )
    pm_sub = parser.add_subparsers(
        dest="courses_package_map_command",
        required=True,
    )

    validate = pm_sub.add_parser(
        "validate",
        help="Validate a logion-package-map.yaml (CLI-local, no network)",
        parents=[COMMON_PARSER],
    )
    validate.add_argument(
        "--dir",
        default=".",
        help="Directory containing the package map (default: .).",
    )
    validate.set_defaults(handler=handle_validate)

    init = pm_sub.add_parser(
        "init",
        help=(
            "Infer and write a logion-package-map.yaml from a local tree "
            "(CLI-local, no network)"
        ),
        parents=[COMMON_PARSER],
    )
    init.add_argument(
        "--dir",
        default=".",
        help="Directory to scan (default: .).",
    )
    init.add_argument(
        "--slug",
        default=None,
        help="Override the inferred package slug.",
    )
    init.add_argument(
        "--yes",
        action="store_true",
        help="Accept the deterministic defaults for all review flags.",
    )
    init.set_defaults(handler=handle_init)
