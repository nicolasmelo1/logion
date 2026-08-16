# SPDX-License-Identifier: MIT
"""Generate internal client operation functions from the OpenAPI contract."""

from __future__ import annotations

import argparse
import builtins
import json
import keyword
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from logion._json import (
    JsonObject,
    as_object,
    child,
    children,
)

ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = ROOT / "contracts" / "openapi" / "v1.json"
OUTPUT_PATH = (
    ROOT
    / "packages"
    / "client"
    / "src"
    / "logion"
    / "v1"
    / "_generated"
    / "operations.py"
)
HTTP_METHODS = {"delete", "get", "patch", "post", "put"}
RESERVED_NAMES = set(keyword.kwlist) | set(dir(builtins))


@dataclass(frozen=True)
class Parameter:
    """OpenAPI parameter needed by a generated operation."""

    wire_name: str
    python_name: str
    location: str
    annotation: str
    required: bool


@dataclass(frozen=True)
class Response:
    """Generated response handling."""

    kind: str
    annotation: str
    model_name: str | None = None


@dataclass(frozen=True)
class Operation:
    """OpenAPI operation needed by the SDK transport layer."""

    operation_id: str
    method: str
    path: str
    path_params: tuple[Parameter, ...]
    query_params: tuple[Parameter, ...]
    request_model: str | None
    response: Response


def main() -> int:
    """Run the operation generator."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Fail if generated operations are not up to date.",
    )
    args = parser.parse_args()

    content = generate_operations()
    if args.check:
        existing = OUTPUT_PATH.read_text() if OUTPUT_PATH.exists() else ""
        if existing != content:
            sys.stderr.write(
                f"{OUTPUT_PATH.relative_to(ROOT)} is out of date. "
                "Run `make -C packages/client generate-operations`.\n"
            )
            return 1
        return 0

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(content)
    return 0


def generate_operations() -> str:
    """Generate the operations module content."""
    spec = as_object(json.loads(CONTRACT_PATH.read_text()), where="contract")
    operations = collect_operations(spec)
    return render_module(operations)


def collect_operations(spec: JsonObject) -> list[Operation]:
    """Extract supported OpenAPI operations in stable order."""
    operations: list[Operation] = []
    paths = child(spec, "paths")
    for path, path_item in sorted(paths.items()):
        if not isinstance(path_item, dict):
            continue
        for method, operation in sorted(path_item.items()):
            if method not in HTTP_METHODS or not isinstance(operation, dict):
                continue
            operations.append(parse_operation(path, method, operation))
    return operations


def parse_operation(
    path: str,
    method: str,
    operation: JsonObject,
) -> Operation:
    """Parse the parts of an OpenAPI operation used by the generator."""
    parameters = [
        parse_parameter(param)
        for param in children(operation, "parameters")
        if param.get("in") in {"path", "query"}
    ]
    request_model = parse_ref(
        child(
            child(child(operation, "requestBody"), "content"),
            "application/json",
        )
    )
    return Operation(
        operation_id=str(operation["operationId"]),
        method=method.upper(),
        path=path,
        path_params=tuple(
            param for param in parameters if param.location == "path"
        ),
        query_params=tuple(
            param for param in parameters if param.location == "query"
        ),
        request_model=request_model,
        response=parse_response(operation),
    )


def parse_parameter(parameter: JsonObject) -> Parameter:
    """Parse a path or query parameter."""
    wire_name = str(parameter["name"])
    annotation = schema_to_annotation(
        child(parameter, "schema"),
        is_path=parameter.get("in") == "path",
    )
    required = bool(parameter.get("required"))
    if not required and annotation != "JsonValue" and "None" not in annotation:
        annotation = f"{annotation} | None"
    return Parameter(
        wire_name=wire_name,
        python_name=to_python_name(wire_name),
        location=str(parameter.get("in", "")),
        annotation=annotation,
        required=required,
    )


def parse_response(operation: JsonObject) -> Response:
    """Parse the preferred JSON success response."""
    responses = child(operation, "responses")
    response: JsonObject = {}
    for status in ("200", "201", "202", "204"):
        response = child(responses, status)
        if response:
            break
    schema = child(
        child(child(response, "content"), "application/json"), "schema"
    )
    model_name = parse_ref_schema(schema)
    if model_name is not None:
        return Response("model", model_name, model_name)
    if schema.get("type") == "array":
        item_model = parse_ref_schema(child(schema, "items"))
        if item_model is not None:
            return Response("list_model", f"list[{item_model}]", item_model)
        return Response("list_dict", "list[JsonObject]")
    if schema.get("type") == "object":
        value_type = schema_to_annotation(
            child(schema, "additionalProperties")
        )
        return Response("dict", f"dict[str, {value_type}]")
    return Response("dict", "JsonObject")


def parse_ref(content: JsonObject) -> str | None:
    """Return the component name referenced by a request-body content."""
    return parse_ref_schema(child(content, "schema"))


def parse_ref_schema(schema: JsonObject) -> str | None:
    """Return the schema component name for a JSON schema $ref."""
    ref = schema.get("$ref")
    if isinstance(ref, str):
        return ref.rsplit("/", maxsplit=1)[-1]
    # Handle anyOf: [{$ref}, {type: null}] — nullable request bodies.
    for item in children(schema, "anyOf"):
        name = parse_ref_schema(item)
        if name is not None:
            return name
    return None


def schema_to_annotation(
    schema: JsonObject,
    *,
    is_path: bool = False,
) -> str:
    """Map a small OpenAPI schema subset to Python annotations."""
    if "anyOf" in schema:
        non_null = [
            item
            for item in children(schema, "anyOf")
            if item.get("type") != "null"
        ]
        if len(non_null) == 1:
            annotation = schema_to_annotation(non_null[0], is_path=is_path)
            return f"{annotation} | None"
        return "JsonValue"
    schema_type = schema.get("type")
    schema_format = schema.get("format")
    if schema_type == "string" and schema_format == "uuid":
        return "str | UUID"
    if schema_type == "string":
        return "str"
    if schema_type == "integer":
        return "int"
    if schema_type == "number":
        return "float"
    if schema_type == "boolean":
        return "bool"
    if schema_type == "array":
        item_type = schema_to_annotation(child(schema, "items"))
        return f"list[{item_type}]"
    if schema_type == "object":
        return "JsonObject"
    return "JsonValue"


def to_python_name(name: str) -> str:
    """Convert a wire parameter name to a valid Python identifier."""
    python_name = re.sub(r"\W", "_", name)
    if python_name in RESERVED_NAMES:
        return f"{python_name}_"
    return python_name


def render_module(operations: list[Operation]) -> str:
    """Render the generated operations module."""
    model_imports = sorted(
        {
            name
            for operation in operations
            for name in (
                operation.request_model,
                operation.response.model_name,
            )
            if name is not None
        },
        key=str.casefold,
    )
    body: list[str] = []
    for index, operation in enumerate(operations):
        if index:
            body.append("")
            body.append("")
        body.extend(render_operation(operation))

    lines = [
        '"""Generated internal operation functions for the v1 API."""',
        "",
        "from __future__ import annotations",
        "",
        "from typing import cast",
        "from uuid import UUID",
        "",
        *render_support_imports(body),
    ]
    if model_imports:
        lines.extend(render_model_imports(model_imports))
    lines.append("")
    lines.append("")
    lines.extend(body)
    lines.append("")
    return "\n".join(lines)


def render_support_imports(body: list[str]) -> list[str]:
    """Render the transport/JSON imports the rendered body actually uses.

    Which of these appear depends on the contract: an API with no
    query parameters needs no ``QueryValue``, and one whose every
    response maps to a model needs neither JSON alias. Emitting them
    unconditionally would leave an unused import for ruff to strip,
    and `--check` would then always report the file as out of date.
    """
    rendered = "\n".join(body)
    http_names = ["HttpClient"]
    if "QueryValue" in rendered:
        http_names.append("QueryValue")
    lines = [f"from logion._http import {', '.join(http_names)}"]

    json_names = [
        name for name in ("JsonObject", "JsonValue") if name in rendered
    ]
    if json_names:
        lines.append(f"from logion._json import {', '.join(json_names)}")
    return lines


def render_model_imports(model_imports: list[str]) -> list[str]:
    """Render imports from the generated Pydantic models module."""
    lines = ["from logion.v1._types.generated.v1 import ("]
    lines.extend(f"    {model_name}," for model_name in model_imports)
    lines.append(")")
    return lines


def render_operation(operation: Operation) -> list[str]:
    """Render one generated function."""
    signature = render_signature(operation)
    return [
        f"def {operation.operation_id}(",
        *signature,
        f") -> {operation.response.annotation}:",
        f'    """Call the {operation.operation_id} API operation."""',
        *render_query_params(operation),
        *render_request(operation),
    ]


def render_signature(operation: Operation) -> list[str]:
    """Render function signature lines."""
    params = [
        *operation.path_params,
        *operation.query_params,
    ]
    lines = ["    http: HttpClient,"]
    if params or operation.request_model is not None:
        lines.append("    *,")
    for param in params:
        default = "" if param.required else " = None"
        lines.append(f"    {param.python_name}: {param.annotation}{default},")
    if operation.request_model is not None:
        lines.append(f"    body: {operation.request_model},")
    return lines


def render_query_params(operation: Operation) -> list[str]:
    """Render query-parameter collection code."""
    if not operation.query_params:
        return []
    lines = ["    params: dict[str, QueryValue] = {}"]
    for param in operation.query_params:
        lines.extend([
            f"    if {param.python_name} is not None:",
            f'        params["{param.wire_name}"] = {param.python_name}',
        ])
    return lines


def render_request(operation: Operation) -> list[str]:
    """Render request and response handling."""
    path = render_path(operation)
    kwargs = render_request_kwargs(operation)
    if operation.response.kind == "model":
        return [
            "    return http.request_model(",
            f'        "{operation.method}",',
            f"        {path},",
            f"        {operation.response.model_name},",
            *kwargs,
            "    )",
        ]
    if operation.response.kind == "list_model":
        return [
            "    return [",
            f"        {operation.response.model_name}.model_validate(item)",
            "        for item in http.request_list(",
            f'            "{operation.method}",',
            f"            {path},",
            *[f"    {line}" for line in kwargs],
            "        )",
            "    ]",
        ]
    if operation.response.kind == "list_dict":
        return [
            "    return http.request_list(",
            f'        "{operation.method}",',
            f"        {path},",
            *kwargs,
            "    )",
        ]
    return [
        "    return cast(",
        f"        {operation.response.annotation},",
        "        http.request(",
        f'            "{operation.method}",',
        f"            {path},",
        *[f"    {line}" for line in kwargs],
        "        ),",
        "    )",
    ]


def render_request_kwargs(operation: Operation) -> list[str]:
    """Render request keyword argument lines."""
    kwargs: list[str] = []
    if operation.query_params:
        kwargs.append("        params=params,")
    json_arg = render_json_arg(operation)
    if json_arg is not None:
        kwargs.append(f"        {json_arg},")
    return kwargs


def render_path(operation: Operation) -> str:
    """Render the request path expression."""
    if not operation.path_params:
        return f'"{operation.path}"'
    path = operation.path
    for param in operation.path_params:
        path = path.replace(
            f"{{{param.wire_name}}}",
            f"{{{param.python_name}}}",
        )
    return f'f"{path}"'


def render_json_arg(operation: Operation) -> str | None:
    """Render the JSON request-body argument."""
    if operation.request_model is None:
        return None
    if operation.operation_id == "update_course":
        return 'json=body.model_dump(mode="json", exclude_unset=True)'
    return 'json=body.model_dump(mode="json", exclude_none=True)'


if __name__ == "__main__":
    raise SystemExit(main())
