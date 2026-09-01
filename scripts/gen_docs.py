#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate the logion.sh/docs artifact from the contract and the CLI tree.

Why this exists as a build step rather than a runtime import: the landing app
deploys with ``packages/landing/`` as its root directory, so it cannot read
``contracts/`` or import the CLI package (the same constraint that makes
``/install.sh`` a redirect to raw GitHub). The reference is therefore compiled
here, where the whole workspace is importable, into one self-contained artifact
the landing renders with no new dependency.

Three sources, none of them prose:

1. ``contracts/openapi/v1.json`` — synced from the private API, hash-locked in
   ``.generated-files.lock``. Nobody can hand-edit it, so the API reference
   cannot drift from the deployed contract without CI noticing.
2. ``cli._parser.build_parser()`` — the single argparse tree the real binary
   builds. Walking it is what ``shtab`` already does for completions.
3. ``logion.v1._operation_map.IMPLEMENTED_OPERATIONS`` — ``operationId`` ->
   ``client.v1.<resource>.<method>``.

The third one is what makes the cross-link possible. Each argparse leaf carries
``set_defaults(handler=...)``, so the chain closes without a hand-written map:

    operationId --(operation map)--> client.v1.x.y --(AST)--> logion <command>

A hand-maintained mapping would rot the first time a handler moved. This one
fails loudly instead, because ``--check`` is wired into CI.

Usage:
  uv run python scripts/gen_docs.py            # regenerate the artifact
  uv run python scripts/gen_docs.py --check    # fail if it is stale
"""

from __future__ import annotations

import argparse
import ast
import difflib
import hashlib
import inspect
import json
import os
import re
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TypedDict

from logion._json import JsonObject, JsonValue

REPO_ROOT = Path(__file__).resolve().parents[1]
OPENAPI_PATH = REPO_ROOT / "contracts" / "openapi" / "v1.json"
COMPAT_PATH = REPO_ROOT / "contracts" / "api-compatibility.json"
GUIDES_DIR = REPO_ROOT / "docs" / "marketplace"
TARGET_PATH = (
    REPO_ROOT / "packages" / "landing" / "landing" / "content" / "docs.json"
)

#: Bumped when the artifact's shape changes in a way the renderer must know
#: about. The landing refuses to render an artifact it does not understand
#: rather than silently dropping fields.
ARTIFACT_VERSION = 1

#: How much of a staleness diff to print. Enough to name what drifted without
#: burying the CI log in a regenerated reference.
_DIFF_PREVIEW_LINES = 60

#: Environment the CLI parser is built under.
#:
#: `logion admin` is gated on LOGION_ENABLE_ADMIN: argparse builds either a
#: 13-command subtree or a single hidden stub depending on it. Read from the
#: ambient environment, the artifact differs between a maintainer's shell and
#: CI — which is exactly the drift this generator exists to prevent. Pinning it
#: here is what makes the output a function of the repository alone.
#:
#: It is pinned *on* rather than off because every admin endpoint is already
#: in the public OpenAPI contract, so documenting the CLI half conceals
#: nothing and keeps the cross-link symmetric. The gate is stated on the page.
_PARSER_ENV = {"LOGION_ENABLE_ADMIN": "1"}

#: Notes rendered under a CLI group heading, for groups whose availability is
#: not what a reader would assume from the command existing.
_GROUP_NOTES = {
    "admin": (
        "> **Gated.** These commands are hidden unless `LOGION_ENABLE_ADMIN` "
        "is set to a truthy value, and the API authorises them separately — "
        "an admin role on the calling key is what actually grants access. "
        "Without the variable the group prints *No such command* and exits 2."
    ),
}

_HTTP_METHODS = ("get", "post", "put", "patch", "delete")


class PageDict(TypedDict):
    """One rendered documentation page, as the landing consumes it."""

    slug: str
    title: str
    summary: str
    kind: str
    body: str


class NavEntry(TypedDict):
    """A sidebar link: enough to render the nav without loading a page."""

    slug: str
    title: str
    summary: str


class SectionDict(TypedDict):
    """One sidebar group."""

    id: str
    title: str
    summary: str
    pages: list[NavEntry]


class SourceDict(TypedDict):
    """Provenance of the artifact, rendered on generated pages."""

    api_major: int | None
    contract_digest: str
    openapi_title: str
    openapi_version: str
    cli_version: str
    operations: int
    cli_commands: int
    linked_operations: int


class Artifact(TypedDict):
    """The whole compiled reference."""

    artifact_version: int
    source: SourceDict
    sections: list[SectionDict]
    pages: dict[str, PageDict]


# The OpenAPI document is a genuine JSON boundary: recursive, heterogeneous,
# and not knowable statically. `JsonObject` says exactly that, and these three
# helpers are how the generator crosses back into concrete types without
# `typing.Any` (banned repo-wide, see pyproject `TID251`).


def _obj(value: JsonValue | None) -> JsonObject:
    return value if isinstance(value, dict) else {}


def _arr(value: JsonValue | None) -> list[JsonValue]:
    return list(value) if isinstance(value, list) else []


def _text(value: JsonValue | None) -> str:
    return value if isinstance(value, str) else ""


_SUMMARY_RE = re.compile(r"^summary:\s*(.+)$", re.MULTILINE)
_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n", re.DOTALL)
_H1_RE = re.compile(r"^# (.+)$", re.MULTILINE)

#: Headers every authenticated route needs. The contract declares no
#: ``securitySchemes`` (FastAPI emits the header as a plain parameter), so the
#: reference states the convention once here instead of repeating a nullable
#: ``authorization`` row on 100+ operations.
_AUTH_HEADER = "authorization"

#: Human-facing names for contract tags. A tag with no entry falls back to a
#: title-cased slug, so a new tag appears in the docs on the next sync without
#: anyone editing this file — it just arrives with a plainer title.
_TAG_TITLES = {
    "admin-agents": "Admin · Agents",
    "admin-bounties": "Admin · Bounties",
    "admin-courses": "Admin · Courses",
    "admin-indexing": "Admin · Indexing",
    "admin-referrals": "Admin · Referrals",
    "admin-reports": "Admin · Reports",
    "admin-users": "Admin · Users",
    "ai-catalog": "AI Catalog",
    "ard": "ARD Discovery",
    "course-reviews": "Course Reviews",
    "indexed-listings": "Indexed Listings",
    "resource_feedback": "Resource Feedback",
}


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------


def _title_for_tag(tag: str) -> str:
    if tag in _TAG_TITLES:
        return _TAG_TITLES[tag]
    return tag.replace("-", " ").replace("_", " ").title()


def _anchor(text: str) -> str:
    """Slugify a heading the way the renderer anchors it."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "section"


def _md_escape(text: str) -> str:
    """Escape the pipe so a value never breaks out of a Markdown table."""
    return text.replace("|", "\\|")


def _code(text: str) -> str:
    return f"`{_md_escape(text)}`"


# --------------------------------------------------------------------------
# OpenAPI schema rendering
# --------------------------------------------------------------------------


class SchemaRenderer:
    """Render contract schemas as readable field tables.

    Kept deliberately shallow. A fully expanded tree of 100+ interlinked
    Pydantic models is unreadable and enormous; one level of properties plus a
    named link to the nested model is what an integrator actually reads.
    """

    def __init__(self, components: JsonObject) -> None:
        self._schemas = _obj(components.get("schemas"))

    def resolve(self, schema: JsonObject) -> tuple[str | None, JsonObject]:
        """Follow a ``$ref`` once, returning ``(model_name, schema)``."""
        ref = schema.get("$ref")
        if not isinstance(ref, str):
            return None, schema
        name = ref.rsplit("/", 1)[-1]
        return name, _obj(self._schemas.get(name))

    def _union_label(self, arms: list[JsonObject]) -> str:
        """``anyOf`` rendered as ``A | B``, plus an optional marker.

        FastAPI spells every nullable field as ``anyOf: [T, null]``, so this
        arm carries most of the contract.
        """
        parts = [
            self.type_label(arm) for arm in arms if arm.get("type") != "null"
        ]
        label = " | ".join(dict.fromkeys(parts)) or "null"
        nullable = any(arm.get("type") == "null" for arm in arms)
        return f"{label}, optional" if nullable else label

    def _scalar_label(self, resolved: JsonObject) -> str:
        """A plain type, an array of one, or a formatted string."""
        kind = resolved.get("type")
        if kind == "array":
            items = resolved.get("items")
            inner = (
                self.type_label(_obj(items))
                if isinstance(items, dict)
                else "unknown"
            )
            return f"{inner}[]"
        if kind == "string" and resolved.get("format"):
            return f"string({_text(resolved.get('format'))})"
        return kind if isinstance(kind, str) else "object"

    def type_label(self, schema: JsonObject) -> str:
        """Describe a schema's type in one short string."""
        name, resolved = self.resolve(schema)
        if name is not None:
            return name

        any_of = _arr(resolved.get("anyOf"))
        if any_of:
            return self._union_label([_obj(entry) for entry in any_of])

        enum = _arr(resolved.get("enum"))
        if enum:
            values = ", ".join(json.dumps(value) for value in enum)
            return f"enum({values})"

        return self._scalar_label(resolved)

    def field_rows(
        self, schema: JsonObject
    ) -> list[tuple[str, str, str, str]]:
        """Return ``(name, type, required, notes)`` for each property."""
        _, resolved = self.resolve(schema)
        properties = _obj(resolved.get("properties"))
        if not properties:
            return []
        required = {
            name
            for name in _arr(resolved.get("required"))
            if isinstance(name, str)
        }
        rows: list[tuple[str, str, str, str]] = []
        for name in sorted(properties):
            prop = _obj(properties[name])
            notes: list[str] = []
            if "default" in prop:
                notes.append(f"default `{json.dumps(prop['default'])}`")
            for bound, label in (
                ("minimum", "min"),
                ("maximum", "max"),
                ("minLength", "min length"),
                ("maxLength", "max length"),
            ):
                if bound in prop:
                    notes.append(f"{label} {prop[bound]}")
            description = _text(prop.get("description"))
            if description:
                notes.insert(0, description)
            rows.append((
                name,
                self.type_label(prop),
                "yes" if name in required else "no",
                "; ".join(notes),
            ))
        return rows

    def table(self, schema: JsonObject, header: str) -> list[str]:
        """Render a model as a Markdown table, or a one-line fallback."""
        rows = self.field_rows(schema)
        name, _ = self.resolve(schema)
        if not rows:
            label = name or self.type_label(schema)
            return [f"{header} `{label}`.", ""]
        lines = [
            f"{header} `{name}`:" if name else f"{header}:",
            "",
            "| Field | Type | Required | Notes |",
            "| --- | --- | --- | --- |",
        ]
        for field, kind, required, notes in rows:
            lines.append(
                f"| `{field}` | {_md_escape(kind)} | {required} "
                f"| {_md_escape(notes)} |"
            )
        lines.append("")
        return lines


# --------------------------------------------------------------------------
# the CLI parser tree
# --------------------------------------------------------------------------


class CliCommand:
    """One invocable leaf of the CLI, with the options it accepts."""

    def __init__(
        self,
        path: list[str],
        parser: argparse.ArgumentParser,
        group: str,
    ) -> None:
        self.path = path
        self.group = group
        self.help = (parser.description or "").strip()
        self.usage = _usage_line(parser, path)
        self.options = _option_rows(parser)
        handler = parser.get_default("handler")
        self.handler = handler
        self.operations: list[str] = []

    @property
    def invocation(self) -> str:
        return "logion " + " ".join(self.path)

    @property
    def anchor(self) -> str:
        # Derived from the rendered heading, not from the path. The heading is
        # "## logion courses get", so its anchor carries the `logion-` prefix;
        # computing it from the path alone silently produced links that 404.
        return _anchor(self.invocation)


def _metavar(action: argparse.Action) -> str:
    """The display name for an argument.

    ``metavar`` is ``str | tuple[str, ...]`` — argparse allows one name per
    ``nargs`` slot — so joining is what keeps a tuple repr out of the usage
    line.
    """
    metavar = action.metavar
    if isinstance(metavar, tuple):
        return " ".join(metavar)
    return metavar or action.dest.upper()


def _usage_line(parser: argparse.ArgumentParser, path: list[str]) -> str:
    """Render the usage line without argparse's terminal-width wrapping."""
    parts = ["logion", *path]
    # argparse exposes no public reader for its actions; shtab walks the same
    # private list to build completions.
    for action in parser._actions:
        if action.dest in ("help", "==SUPPRESS=="):
            continue
        if not action.option_strings:
            name = _metavar(action)
            parts.append(name if action.required else f"[{name}]")
            continue
        flag = action.option_strings[-1]
        if action.nargs == 0 or isinstance(
            action, argparse._StoreTrueAction | argparse._StoreFalseAction
        ):
            token = flag
        else:
            token = f"{flag} {_metavar(action).upper()}"
        parts.append(token if action.required else f"[{token}]")
    return " ".join(parts)


def _option_rows(
    parser: argparse.ArgumentParser,
) -> list[tuple[str, str, str, str]]:
    """Return ``(flags, value, default, help)`` for every documented option."""
    rows: list[tuple[str, str, str, str]] = []
    for action in parser._actions:
        if action.dest == "help" or action.help == argparse.SUPPRESS:
            continue
        flags = ", ".join(action.option_strings) or _metavar(action)
        if action.choices:
            value = " \\| ".join(str(choice) for choice in action.choices)
        elif action.nargs == 0 or isinstance(
            action, argparse._StoreTrueAction | argparse._StoreFalseAction
        ):
            value = "flag"
        else:
            kind = getattr(action.type, "__name__", None)
            value = kind or "string"
        default = ""
        if action.default not in (None, argparse.SUPPRESS, False):
            default = f"`{action.default}`"
        rows.append((flags, value, default, (action.help or "").strip()))
    return rows


def walk_parser(
    parser: argparse.ArgumentParser,
    path: list[str] | None = None,
    group: str | None = None,
) -> Iterator[CliCommand]:
    """Yield every invocable leaf of the parser tree, depth-first."""
    path = path or []
    subparser_actions = [
        action
        for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ]
    if not subparser_actions:
        if path:
            yield CliCommand(path, parser, group or path[0])
        return
    seen: set[str] = set()
    for action in subparser_actions:
        for name, child in action.choices.items():
            # argparse registers aliases as separate keys pointing at one
            # parser object. Documenting a command once per alias would
            # triple some groups, so dedupe them.
            #
            # Keyed on `prog` rather than `id()`: object ids are only unique
            # among live objects, so an identity set is a correctness argument
            # about the garbage collector rather than about the parser tree.
            # `prog` is the parser's own name and is stable across runs, which
            # a generated artifact compared byte-for-byte in CI depends on.
            if child.prog in seen:
                continue
            seen.add(child.prog)
            yield from walk_parser(child, [*path, name], group or name)


# --------------------------------------------------------------------------
# CLI command -> API operation, by AST
# --------------------------------------------------------------------------


def _attribute_chain(node: ast.AST) -> str | None:
    """Flatten ``client.v1.listings.search`` into a dotted string."""
    parts: list[str] = []
    current = node
    while isinstance(current, ast.Attribute):
        parts.append(current.attr)
        current = current.value
    if not isinstance(current, ast.Name):
        return None
    parts.append(current.id)
    return ".".join(reversed(parts))


class _SdkCallVisitor(ast.NodeVisitor):
    """Collect ``client.v1.*`` call targets and same-module helper calls."""

    def __init__(self) -> None:
        self.sdk_calls: set[str] = set()
        self.local_calls: set[str] = set()

    def visit_Call(self, node: ast.Call) -> None:
        chain = _attribute_chain(node.func)
        if chain and ".v1." in chain:
            # Normalise the receiver. Handlers bind the client to several
            # names (`client`, `_client`, `api`); the operation map always
            # spells it `client`, so only the part after `.v1.` is identity.
            tail = chain.split(".v1.", 1)[1]
            self.sdk_calls.add(f"client.v1.{tail}")
        elif isinstance(node.func, ast.Name):
            self.local_calls.add(node.func.id)
        self.generic_visit(node)


def _module_functions(tree: ast.Module) -> dict[str, ast.FunctionDef]:
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def sdk_calls_for(handler: Callable[..., object] | None) -> set[str]:
    """Return the ``client.v1.x.y`` targets a handler reaches.

    Resolves one hop into same-module helpers, because several handlers are a
    thin dispatch over a private ``_do_thing`` in the same file. Going deeper
    buys nothing and starts producing false links.
    """
    if handler is None:
        return set()
    try:
        source = inspect.getsource(sys.modules[handler.__module__])
    except (OSError, KeyError, TypeError):
        return set()
    tree = ast.parse(source)
    functions = _module_functions(tree)
    entry = functions.get(handler.__name__)
    if entry is None:
        return set()

    visitor = _SdkCallVisitor()
    visitor.visit(entry)
    found = set(visitor.sdk_calls)
    for name in visitor.local_calls:
        helper = functions.get(name)
        if helper is None:
            continue
        nested = _SdkCallVisitor()
        nested.visit(helper)
        found |= nested.sdk_calls
    return found


# --------------------------------------------------------------------------
# page builders
# --------------------------------------------------------------------------


def _json_schema(container: JsonObject) -> JsonObject:
    """The ``application/json`` schema of a request body or response."""
    content = _obj(container.get("content"))
    return _obj(_obj(content.get("application/json")).get("schema"))


def _parameter_lines(
    operation: JsonObject, renderer: SchemaRenderer
) -> list[str]:
    parameters = [_obj(entry) for entry in _arr(operation.get("parameters"))]
    lines: list[str] = []
    if any(param.get("name") == _AUTH_HEADER for param in parameters):
        lines.append(
            "Takes an [`Authorization`](/docs/api/overview#authentication) "
            "header."
        )
        lines.append("")
    visible = [p for p in parameters if p.get("name") != _AUTH_HEADER]
    if not visible:
        return lines
    lines.append("**Parameters**")
    lines.append("")
    lines.append("| Name | In | Type | Required |")
    lines.append("| --- | --- | --- | --- |")
    for param in visible:
        label = renderer.type_label(_obj(param.get("schema")))
        lines.append(
            f"| `{_text(param.get('name'))}` | {_text(param.get('in'))} "
            f"| {_md_escape(label)} "
            f"| {'yes' if param.get('required') else 'no'} |"
        )
    lines.append("")
    return lines


def _response_lines(
    operation: JsonObject, renderer: SchemaRenderer
) -> list[str]:
    responses = _obj(operation.get("responses"))
    if not responses:
        return []
    lines = [
        "**Responses**",
        "",
        "| Status | Meaning | Schema |",
        "| --- | --- | --- |",
    ]
    for status in sorted(responses):
        entry = _obj(responses[status])
        schema = _json_schema(entry)
        name = renderer.resolve(schema)[0] if schema else None
        lines.append(
            f"| `{status}` | {_md_escape(_text(entry.get('description')))} "
            f"| {f'`{name}`' if name else '—'} |"
        )
    lines.append("")
    success = next((s for s in sorted(responses) if s.startswith("2")), None)
    if success:
        schema = _json_schema(_obj(responses[success]))
        if schema:
            lines.extend(renderer.table(schema, "Returns"))
    return lines


def _operation_page_lines(
    path: str,
    method: str,
    operation: JsonObject,
    renderer: SchemaRenderer,
    cli_for_operation: dict[str, list[tuple[str, str]]],
) -> list[str]:
    op_id = _text(operation.get("operationId"))
    title = (
        _text(operation.get("summary")) or op_id or f"{method.upper()} {path}"
    )
    lines = [f"## {title}", ""]
    lines.append(f"```http\n{method.upper()} {path}\n```")
    lines.append("")
    description = _text(operation.get("description")).strip()
    if description:
        lines.append(description)
        lines.append("")
    if op_id:
        lines.append(f"Operation id: `{op_id}`")
        lines.append("")

    lines.extend(_parameter_lines(operation, renderer))

    body_schema = _json_schema(_obj(operation.get("requestBody")))
    if body_schema:
        lines.append("**Request body**")
        lines.append("")
        lines.extend(renderer.table(body_schema, "Body"))

    lines.extend(_response_lines(operation, renderer))

    commands = cli_for_operation.get(op_id, [])
    if commands:
        lines.append("**From the CLI**")
        lines.append("")
        for invocation, target in commands:
            lines.append(f"- [`{invocation}`](/docs/{target})")
        lines.append("")
    return lines


#: One operation as the page builders pass it around: path, method, body.
Operation = tuple[str, str, JsonObject]


def _operation_heading(path: str, method: str, operation: JsonObject) -> str:
    """The h2 an operation renders under. Its anchor is derived from this."""
    return (
        _text(operation.get("summary"))
        or _text(operation.get("operationId"))
        or f"{method.upper()} {path}"
    )


def _group_operations_by_tag(spec: JsonObject) -> dict[str, list[Operation]]:
    """Bucket every contract operation under each tag it declares."""
    by_tag: dict[str, list[Operation]] = {}
    for path, methods in _obj(spec.get("paths")).items():
        for method, raw in _obj(methods).items():
            if method not in _HTTP_METHODS:
                continue
            operation = _obj(raw)
            tags = [
                tag
                for tag in _arr(operation.get("tags"))
                if isinstance(tag, str)
            ] or ["general"]
            for tag in tags:
                by_tag.setdefault(tag, []).append((path, method, operation))
    return by_tag


def _api_page_body(
    title: str,
    operations: list[Operation],
    renderer: SchemaRenderer,
    cli_for_operation: dict[str, list[tuple[str, str]]],
) -> str:
    """A tag page: a contents list, then every operation in full."""
    plural = "s" if len(operations) != 1 else ""
    lines = [
        f"# {title}",
        "",
        f"{len(operations)} operation{plural} on the Logion v1 API.",
        "",
    ]
    for path, method, operation in operations:
        heading = _operation_heading(path, method, operation)
        lines.append(
            f"- [{heading}](#{_anchor(heading)}) — `{method.upper()} {path}`"
        )
    lines.append("")
    for path, method, operation in operations:
        lines.extend(
            _operation_page_lines(
                path, method, operation, renderer, cli_for_operation
            )
        )
    return "\n".join(lines).rstrip() + "\n"


def build_api_pages(
    spec: JsonObject,
    cli_for_operation: dict[str, list[tuple[str, str]]],
) -> tuple[list[PageDict], dict[str, str]]:
    """Return one page per contract tag, plus operationId -> page anchor."""
    renderer = SchemaRenderer(_obj(spec.get("components")))
    by_tag = _group_operations_by_tag(spec)

    pages: list[PageDict] = []
    slug_for_operation: dict[str, str] = {}
    for tag in sorted(by_tag):
        operations = sorted(by_tag[tag], key=lambda item: (item[0], item[1]))
        slug = f"api/{tag.replace('_', '-')}"
        title = _title_for_tag(tag)
        plural = "s" if len(operations) != 1 else ""
        for path, method, operation in operations:
            op_id = _text(operation.get("operationId"))
            if op_id:
                heading = _operation_heading(path, method, operation)
                slug_for_operation[op_id] = f"{slug}#{_anchor(heading)}"
        pages.append({
            "slug": slug,
            "title": title,
            "summary": (
                f"{len(operations)} API operation{plural} tagged `{tag}`."
            ),
            "kind": "api",
            "body": _api_page_body(
                title, operations, renderer, cli_for_operation
            ),
        })
    return pages, slug_for_operation


def _command_lines(
    command: CliCommand, slug_for_operation: dict[str, str]
) -> list[str]:
    """One command: heading, usage, options, and the endpoint it calls."""
    lines = [f"## {command.invocation}", ""]
    if command.help:
        lines.append(command.help)
        lines.append("")
    lines.append(f"```bash\n{command.usage}\n```")
    lines.append("")
    if command.options:
        lines.append("| Option | Value | Default | Description |")
        lines.append("| --- | --- | --- | --- |")
        for flags, value, default, help_text in command.options:
            lines.append(
                f"| `{flags}` | {value} | {default or '—'} "
                f"| {_md_escape(help_text)} |"
            )
        lines.append("")
    if command.operations:
        lines.append("**Calls**")
        lines.append("")
        for op_id in command.operations:
            target = slug_for_operation.get(op_id)
            link = f"[`{op_id}`](/docs/{target})" if target else f"`{op_id}`"
            lines.append(f"- {link}")
        lines.append("")
    return lines


def _cli_page_body(
    group: str,
    commands: list[CliCommand],
    slug_for_operation: dict[str, str],
) -> str:
    """A group page: a contents list, then every command in full."""
    plural = "s" if len(commands) != 1 else ""
    lines = [
        f"# logion {group}",
        "",
        f"{len(commands)} command{plural} in this group.",
        "",
    ]
    note = _GROUP_NOTES.get(group)
    if note:
        lines.append(note)
        lines.append("")
    for command in commands:
        suffix = f" — {command.help}" if command.help else ""
        lines.append(f"- [`{command.invocation}`](#{command.anchor}){suffix}")
    lines.append("")
    for command in commands:
        lines.extend(_command_lines(command, slug_for_operation))
    return "\n".join(lines).rstrip() + "\n"


def build_cli_pages(
    commands: list[CliCommand],
    slug_for_operation: dict[str, str],
) -> list[PageDict]:
    """Return one page per top-level command group."""
    by_group: dict[str, list[CliCommand]] = {}
    for command in commands:
        by_group.setdefault(command.group, []).append(command)

    pages: list[PageDict] = []
    for group in sorted(by_group):
        group_commands = sorted(by_group[group], key=lambda c: c.path)
        plural = "s" if len(group_commands) != 1 else ""
        pages.append({
            "slug": f"cli/{group}",
            "title": f"logion {group}",
            "summary": f"{len(group_commands)} CLI command{plural}.",
            "kind": "cli",
            "body": _cli_page_body(group, group_commands, slug_for_operation),
        })
    return pages


def build_guide_pages() -> list[PageDict]:
    """Return the hand-written guides, unchanged, from ``docs/marketplace``."""
    pages: list[PageDict] = []
    for path in sorted(GUIDES_DIR.glob("*.md")):
        raw = path.read_text(encoding="utf-8")
        summary_match = _SUMMARY_RE.search(raw)
        body = _FRONTMATTER_RE.sub("", raw)
        title_match = _H1_RE.search(body)
        pages.append({
            "slug": f"guides/{path.stem}",
            "title": (title_match.group(1) if title_match else path.stem),
            "summary": (
                summary_match.group(1).strip() if summary_match else ""
            ),
            "kind": "guide",
            "body": body.strip() + "\n",
        })
    return pages


def build_overviews(
    compat: JsonObject,
    api_pages: list[PageDict],
    cli_pages: list[PageDict],
    linked: int,
    total_operations: int,
) -> list[PageDict]:
    """Return the three landing pages of the reference."""
    api_lines = [
        "# API Reference",
        "",
        f"The Logion v1 API: **{total_operations} operations** across "
        f"**{len(api_pages)} groups**, generated from the published OpenAPI "
        "contract.",
        "",
        "This page and every page under it are generated from "
        "`contracts/openapi/v1.json`, which is produced by the API itself and "
        "hash-locked in the repository. Nobody can edit it by hand, so the "
        "reference cannot describe an endpoint the deployed API does not "
        "serve.",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| API major | `{compat.get('api_major', '—')}` |",
        f"| Contract digest | `{compat.get('contract_digest', '—')}` |",
        f"| Minimum CLI | `{compat.get('minimum_cli_version', '—')}` |",
        f"| Current CLI | `{compat.get('current_cli_version', '—')}` |",
        "",
        "## Authentication",
        "",
        "An API key travels in a bearer header:",
        "",
        "```http",
        "Authorization: Bearer lg_…",
        "```",
        "",
        "`logion identity onboarding` provisions a key, and the CLI sends it "
        "for you — which is the reason to prefer a command over a raw call.",
        "",
        "**One honest limit.** The contract marks this header optional on "
        "every route that accepts it, because the API enforces authentication "
        "in the handler rather than in the schema. So this reference can tell "
        "you which operations *take* a key, and cannot tell you which ones "
        "*reject* an anonymous call. Assume any operation that lists the "
        "header needs one. Nothing here guesses past what the contract "
        "actually states.",
        "",
        "## Groups",
        "",
        "| Group | Operations |",
        "| --- | --- |",
    ]
    for page in api_pages:
        api_lines.append(
            f"| [{page['title']}](/docs/{page['slug']}) | {page['summary']} |"
        )
    api_lines.append("")

    cli_lines = [
        "# CLI Reference",
        "",
        f"Every command the `logion` binary accepts: **{len(cli_pages)} "
        "groups**, generated by walking the same argparse tree the binary "
        "builds at runtime.",
        "",
        "The CLI is the execution layer. It sends the API key, retries, and "
        "renders JSON, so an agent should reach for a command before an HTTP "
        "call.",
        "",
        "```bash",
        "curl -fsSL https://logion.sh/install.sh | sh",
        "logion --help",
        "```",
        "",
        f"**{linked} of {total_operations} API operations** are reachable "
        "from a command, and each one links to the other. The mapping is "
        "derived from the code, not maintained by hand — see "
        "[How these docs stay true]"
        "(/docs/reference/how-these-docs-are-built).",
        "",
        "## Groups",
        "",
        "| Group | Commands |",
        "| --- | --- |",
    ]
    for page in cli_pages:
        cli_lines.append(
            f"| [{page['title']}](/docs/{page['slug']}) | {page['summary']} |"
        )
    cli_lines.append("")

    provenance = [
        "# How these docs are built",
        "",
        "Documentation that is written by hand drifts from the software it "
        "describes, and the drift is invisible until somebody follows an "
        "instruction that no longer works. Everything under **API Reference** "
        "and **CLI Reference** is therefore generated, and CI fails when the "
        "generated output stops matching the source.",
        "",
        "## The three sources",
        "",
        "| Section | Generated from | Who produces it |",
        "| --- | --- | --- |",
        "| API Reference | `contracts/openapi/v1.json` | the API, exported on "
        "merge and hash-locked in `.generated-files.lock` |",
        "| CLI Reference | `cli._parser.build_parser()` | the same argparse "
        "tree the installed binary builds |",
        "| Guides | `docs/marketplace/*.md` | written by hand, the only prose "
        "here |",
        "",
        "## How the two references are cross-linked",
        "",
        "The link between a command and the endpoint it calls is derived, not "
        "declared. A hand-maintained table would rot the first time a handler "
        "moved; this chain breaks loudly instead.",
        "",
        "```text",
        "operationId",
        "  │  logion.v1._operation_map.IMPLEMENTED_OPERATIONS",
        "  ▼",
        "client.v1.<resource>.<method>",
        "  │  AST scan of the handler each argparse leaf registers",
        "  ▼",
        "logion <command>",
        "```",
        "",
        "Each argparse leaf carries `set_defaults(handler=…)`, so the "
        "generator resolves a command to a real function, parses that "
        "function, and collects the SDK calls it makes. Reversing the "
        "operation map turns those into operation ids.",
        "",
        "## Staleness is a build failure",
        "",
        "```bash",
        "make docs-generate        # rewrite the artifact",
        "uv run python scripts/gen_docs.py --check   # what CI runs",
        "```",
        "",
        "The check recomputes the artifact and compares it byte for byte. A "
        "contract sync that adds an endpoint, or a new CLI flag, turns the "
        "build red until the docs are regenerated — which is the only thing "
        "that makes *“the docs are current”* a fact rather than a hope.",
        "",
        "## What is not generated",
        "",
        "The guides are prose and stay prose. Generated reference tells you "
        "what exists; it cannot tell you why, or which of two endpoints you "
        "want. Both are needed and neither substitutes for the other.",
        "",
    ]

    return [
        {
            "slug": "api/overview",
            "title": "API Reference",
            "summary": (
                f"{total_operations} operations across {len(api_pages)} "
                "groups, generated from the OpenAPI contract."
            ),
            "kind": "api",
            "body": "\n".join(api_lines).rstrip() + "\n",
        },
        {
            "slug": "cli/overview",
            "title": "CLI Reference",
            "summary": (
                f"{len(cli_pages)} command groups, generated from the "
                "argparse tree."
            ),
            "kind": "cli",
            "body": "\n".join(cli_lines).rstrip() + "\n",
        },
        {
            "slug": "reference/how-these-docs-are-built",
            "title": "How these docs are built",
            "summary": (
                "The three sources, the cross-link chain, and why staleness "
                "is a build failure."
            ),
            "kind": "meta",
            "body": "\n".join(provenance).rstrip() + "\n",
        },
    ]


def build_index_page(sections: list[SectionDict]) -> PageDict:
    lines = [
        "# Logion documentation",
        "",
        "Logion measures whether the skills, plugins, MCP servers and models "
        "an agent installs actually do what they claim, and publishes the "
        "method so anyone can reproduce it.",
        "",
        "Two references and a set of guides. The references are generated "
        "from the contract and the CLI itself, so they cannot drift — see "
        "[How these docs are built]"
        "(/docs/reference/how-these-docs-are-built).",
        "",
    ]
    for section in sections:
        lines.append(f"## {section['title']}")
        lines.append("")
        if section["summary"]:
            lines.append(section["summary"])
            lines.append("")
        for page in section["pages"]:
            entry = f"- [{page['title']}](/docs/{page['slug']})"
            if page["summary"]:
                entry += f" — {page['summary']}"
            lines.append(entry)
        lines.append("")
    return {
        "slug": "index",
        "title": "Documentation",
        "summary": "Guides, API reference, and CLI reference.",
        "kind": "index",
        "body": "\n".join(lines).rstrip() + "\n",
    }


# --------------------------------------------------------------------------
# assembly
# --------------------------------------------------------------------------


def _nav_entries(pages: list[PageDict]) -> list[NavEntry]:
    """Sidebar entries for a list of pages."""
    return [
        {
            "slug": page["slug"],
            "title": page["title"],
            "summary": page["summary"],
        }
        for page in pages
    ]


def build_artifact() -> Artifact:
    """Compile the whole documentation artifact from its three sources."""
    # Pin the parser environment before importing the CLI: registration reads
    # it at build_parser() time, so the artifact would otherwise depend on
    # whoever ran the generator. See _PARSER_ENV.
    os.environ.update(_PARSER_ENV)

    # Imported lazily: this runs under the workspace venv where both packages
    # are installed, and importing the CLI at module scope would make a plain
    # `--help` pay for the whole command tree.
    from cli._parser import build_parser
    from cli._version import __version__ as cli_version
    from logion.v1._operation_map import IMPLEMENTED_OPERATIONS

    spec: JsonObject = _obj(
        json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))
    )
    compat: JsonObject = _obj(
        json.loads(COMPAT_PATH.read_text(encoding="utf-8"))
    )

    operation_for_sdk_path = {
        target: op_id for op_id, target in IMPLEMENTED_OPERATIONS.items()
    }

    commands = list(walk_parser(build_parser()))
    cli_for_operation: dict[str, list[tuple[str, str]]] = {}
    for command in commands:
        for target in sorted(sdk_calls_for(command.handler)):
            op_id = operation_for_sdk_path.get(target)
            if op_id is None:
                continue
            command.operations.append(op_id)
            cli_for_operation.setdefault(op_id, []).append((
                command.invocation,
                f"cli/{command.group}#{command.anchor}",
            ))
    for entries in cli_for_operation.values():
        entries.sort()

    total_operations = sum(
        1
        for methods in _obj(spec.get("paths")).values()
        for method in _obj(methods)
        if method in _HTTP_METHODS
    )

    api_pages, slug_for_operation = build_api_pages(spec, cli_for_operation)
    cli_pages = build_cli_pages(commands, slug_for_operation)
    guide_pages = build_guide_pages()
    overviews = build_overviews(
        compat,
        api_pages,
        cli_pages,
        len(cli_for_operation),
        total_operations,
    )
    api_overview, cli_overview, provenance = overviews

    sections: list[SectionDict] = [
        {
            "id": "guides",
            "title": "Guides",
            "summary": "Written by hand. Start here.",
            "pages": _nav_entries(guide_pages),
        },
        {
            "id": "api",
            "title": "API Reference",
            "summary": api_overview["summary"],
            "pages": [
                {
                    "slug": api_overview["slug"],
                    "title": "Overview",
                    "summary": api_overview["summary"],
                },
                *_nav_entries(api_pages),
            ],
        },
        {
            "id": "cli",
            "title": "CLI Reference",
            "summary": cli_overview["summary"],
            "pages": [
                {
                    "slug": cli_overview["slug"],
                    "title": "Overview",
                    "summary": cli_overview["summary"],
                },
                *_nav_entries(cli_pages),
            ],
        },
        {
            "id": "reference",
            "title": "About",
            "summary": "How this documentation stays true.",
            "pages": [
                {
                    "slug": provenance["slug"],
                    "title": provenance["title"],
                    "summary": provenance["summary"],
                }
            ],
        },
    ]

    all_pages = [
        build_index_page(sections),
        *guide_pages,
        api_overview,
        *api_pages,
        cli_overview,
        *cli_pages,
        provenance,
    ]

    info = _obj(spec.get("info"))
    api_major = compat.get("api_major")
    source: SourceDict = {
        "api_major": api_major if isinstance(api_major, int) else None,
        "contract_digest": _text(compat.get("contract_digest")),
        "openapi_title": _text(info.get("title")),
        "openapi_version": _text(info.get("version")),
        "cli_version": cli_version,
        "operations": total_operations,
        "cli_commands": len(commands),
        "linked_operations": len(cli_for_operation),
    }
    return {
        "artifact_version": ARTIFACT_VERSION,
        "source": source,
        "sections": sections,
        "pages": {page["slug"]: page for page in all_pages},
    }


def serialize(artifact: Artifact) -> str:
    rendered = json.dumps(
        artifact, indent=2, sort_keys=True, ensure_ascii=False
    )
    return rendered + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail when the committed artifact is stale.",
    )
    args = parser.parse_args()

    rendered = serialize(build_artifact())
    if not args.check:
        TARGET_PATH.parent.mkdir(parents=True, exist_ok=True)
        TARGET_PATH.write_text(rendered, encoding="utf-8")
        digest = hashlib.sha256(rendered.encode("utf-8")).hexdigest()
        target = TARGET_PATH.relative_to(REPO_ROOT)
        print(f"wrote {target} sha256:{digest[:16]}")
        return 0

    if not TARGET_PATH.exists():
        print(
            "docs artifact missing; run `make docs-generate`", file=sys.stderr
        )
        return 1
    committed = TARGET_PATH.read_text(encoding="utf-8")
    if committed != rendered:
        print(
            "docs artifact is stale — the contract or the CLI moved and "
            "the documentation did not.\n"
            "Run `make docs-generate` and commit the result.\n",
            file=sys.stderr,
        )
        # Show what moved. "Stale" on its own sends the reader to re-run the
        # generator and eyeball a 400 KB JSON diff; naming the drifting keys
        # is the difference between a one-minute fix and an afternoon.
        diff = difflib.unified_diff(
            committed.splitlines(),
            rendered.splitlines(),
            fromfile="committed",
            tofile="regenerated",
            lineterm="",
            n=1,
        )
        for line in list(diff)[:_DIFF_PREVIEW_LINES]:
            print(line, file=sys.stderr)
        return 1
    print("docs artifact is current.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
